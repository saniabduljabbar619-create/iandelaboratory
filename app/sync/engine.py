# -*- coding: utf-8 -*-
# app/sync/engine.py
"""
Core of LAN <-> cloud sync. The same code runs on both nodes:

  collect_outgoing()  — read pending sync_outbox rows and serialize the
                        current state of each changed row
  apply_incoming()    — write a batch of changes from the other node

Row identity: every synced row has a global sync id kept in sync_map.
  * rows created while sync is on get a fresh id when first inserted
  * rows that existed when the LAN copy was taken from the cloud have the
    same integer id on both nodes and use the id "seed:<table>:<id>"

Conflicts: if both nodes changed the same row since they last synced, the
newer change wins (ties go to the LAN server). A row deleted on one node
stays deleted.
"""
from __future__ import annotations

import logging
import uuid
from collections import OrderedDict
from datetime import date, datetime
from decimal import Decimal
from enum import Enum as PyEnum

from sqlalchemy import Date, DateTime, Numeric, delete, func, insert, select, update
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

import app.models  # noqa: F401  (registers every table on Base.metadata)
from app.core.config import settings
from app.db.base import Base
from app.sync.models import SyncMap, SyncOutbox
from app.sync.registry import RANK, TableSpec, spec_for

log = logging.getLogger("solunex.sync")

MAP = SyncMap.__table__
OUTBOX = SyncOutbox.__table__
SEED_PREFIX = "seed:"


class SyncError(Exception):
    pass


def table_of(name: str):
    return Base.metadata.tables[name]


def utcnow() -> datetime:
    return datetime.utcnow()


# --------------------------------------------------
# SYNC IDS
# --------------------------------------------------

def new_sync_id() -> str:
    return str(uuid.uuid4())


def add_map(conn, table: str, local_id: int, sync_id: str) -> None:
    conn.execute(insert(MAP).values(table_name=table, local_id=local_id, sync_id=sync_id))


def local_sync_id(conn, table: str, local_id: int) -> str:
    """Global sync id for a local row, creating the seed mapping on first use."""
    row = conn.execute(
        select(MAP.c.sync_id)
        .where(MAP.c.table_name == table, MAP.c.local_id == local_id)
        .order_by(MAP.c.id)
        .limit(1)
    ).first()
    if row:
        return row[0]

    sid = f"{SEED_PREFIX}{table}:{local_id}"
    taken = conn.execute(select(MAP.c.local_id).where(MAP.c.sync_id == sid)).first()
    if taken:
        # The seed id already names a different local row; give this one a fresh id.
        sid = new_sync_id()
    add_map(conn, table, local_id, sid)
    return sid


def _row_exists(conn, table: str, local_id: int) -> bool:
    t = table_of(table)
    return conn.execute(select(t.c.id).where(t.c.id == local_id)).first() is not None


def resolve(conn, table: str, sync_id: str) -> tuple[int | None, bool]:
    """
    Local id for a sync id -> (local_id, exists).
    (id, False) means the row was known here but has since been deleted.
    """
    row = conn.execute(
        select(MAP.c.local_id).where(MAP.c.sync_id == sync_id, MAP.c.table_name == table)
    ).first()
    if row:
        return row[0], _row_exists(conn, table, row[0])

    # A row that existed when the LAN copy was made: same integer id on both
    # nodes. Trust it only if the local row is not already mapped to some
    # other sync id (which would mean it is a different row).
    if sync_id.startswith(SEED_PREFIX):
        try:
            seed_table, seed_id = sync_id[len(SEED_PREFIX):].rsplit(":", 1)
            seed_id = int(seed_id)
        except ValueError:
            return None, False
        if seed_table == table and _row_exists(conn, table, seed_id):
            mapped = conn.execute(
                select(MAP.c.id).where(MAP.c.table_name == table, MAP.c.local_id == seed_id)
            ).first()
            if not mapped:
                add_map(conn, table, seed_id, sync_id)
                return seed_id, True
    return None, False


# --------------------------------------------------
# OUTBOX (written by capture.py)
# --------------------------------------------------

def record_change(conn, table: str, row_id: int, sync_id: str, op: str) -> None:
    conn.execute(insert(OUTBOX).values(
        table_name=table, row_id=row_id, sync_id=sync_id, op=op, changed_at=utcnow(),
    ))


def pending_count(conn) -> int:
    return conn.execute(select(func.count()).select_from(OUTBOX)).scalar() or 0


# --------------------------------------------------
# ENCODE / DECODE
# --------------------------------------------------

def _encode_scalar(v):
    if isinstance(v, (datetime, date)):
        return v.isoformat()
    if isinstance(v, Decimal):
        return str(v)
    if isinstance(v, PyEnum):
        return v.value
    if isinstance(v, bytes):
        return v.decode("utf-8", errors="replace")
    return v


def _decode_scalar(col, v):
    if v is None:
        return None
    ctype = col.type
    if isinstance(ctype, DateTime) and isinstance(v, str):
        dt = datetime.fromisoformat(v)
        return dt.replace(tzinfo=None) if dt.tzinfo else dt
    if isinstance(ctype, Date) and not isinstance(ctype, DateTime) and isinstance(v, str):
        return date.fromisoformat(v[:10])
    if isinstance(ctype, Numeric) and getattr(ctype, "asdecimal", True) and isinstance(v, (str, int, float)):
        return Decimal(str(v))
    enum_class = getattr(ctype, "enum_class", None)
    if enum_class is not None and isinstance(v, str):
        try:
            return enum_class(v)
        except ValueError:
            return enum_class[v]
    return v


def _parse_csv_ids(raw) -> list[int]:
    out = []
    for part in str(raw or "").split(","):
        part = part.strip()
        if part.isdigit():
            out.append(int(part))
    return out


def serialize_row(conn, spec: TableSpec, row) -> dict:
    t = table_of(spec.table)
    data = {}
    for col in t.columns:
        name = col.name
        if name == "id" or name in spec.exclude:
            continue
        v = row[name]
        if v is None:
            data[name] = None
        elif name in spec.fks:
            data[name] = local_sync_id(conn, spec.fks[name], v)
        elif name in spec.poly:
            type_col, targets = spec.poly[name]
            target = targets.get(row[type_col])
            # Known reference types travel as sync ids (str); anything else keeps its raw int.
            data[name] = local_sync_id(conn, target, v) if target else v
        elif name in spec.csv_fks:
            data[name] = [local_sync_id(conn, spec.csv_fks[name], i) for i in _parse_csv_ids(v)]
        else:
            data[name] = _encode_scalar(v)
    return data


def decode_row(conn, spec: TableSpec, data: dict) -> tuple[dict, list[str]]:
    """Returns (column values for the local table, columns whose references are not resolvable yet)."""
    t = table_of(spec.table)
    values, unresolved = {}, []
    for name, v in data.items():
        if name == "id" or name in spec.exclude or name not in t.c:
            continue  # tolerate small schema differences between nodes
        col = t.c[name]
        if v is None:
            values[name] = None
        elif name in spec.fks:
            lid, _ = resolve(conn, spec.fks[name], v)
            if lid is None:
                unresolved.append(name)
            else:
                values[name] = lid
        elif name in spec.poly:
            type_col, targets = spec.poly[name]
            target = targets.get(data.get(type_col))
            if target and isinstance(v, str):
                lid, _ = resolve(conn, target, v)
                values[name] = lid  # informational pointer; None if the target never arrives
            else:
                values[name] = v
        elif name in spec.csv_fks:
            ids = [resolve(conn, spec.csv_fks[name], sid)[0] for sid in (v or [])]
            if any(i is None for i in ids):
                unresolved.append(name)
            values[name] = ",".join(str(i) for i in ids if i is not None) or None
        elif name in spec.files:
            values[name] = str(v).replace("\\", "/")
        else:
            values[name] = _decode_scalar(col, v)
    return values, unresolved


# --------------------------------------------------
# COLLECT (sender side)
# --------------------------------------------------

def collect_outgoing(conn, limit: int) -> tuple[list[dict], list[int]]:
    """
    Pending changes, oldest first, with several edits to one row merged into
    its current state. Returns (changes, outbox ids covered).
    """
    rows = conn.execute(select(OUTBOX).order_by(OUTBOX.c.id).limit(limit)).mappings().all()
    groups: "OrderedDict[tuple, dict]" = OrderedDict()
    ids = []
    for r in rows:
        ids.append(r["id"])
        key = (r["table_name"], r["row_id"])
        g = groups.setdefault(key, {"first": r["id"]})
        g.update(table=r["table_name"], row_id=r["row_id"], sync_id=r["sync_id"],
                 op=r["op"], changed_at=r["changed_at"])

    changes = []
    for g in groups.values():
        spec = spec_for(g["table"])
        if not spec:
            continue
        if settings.NODE_ROLE == "cloud" and spec.direction == "up":
            continue  # the LAN server is the authority for these
        change = {
            "table": g["table"],
            "sync_id": g["sync_id"],
            "op": g["op"],
            "changed_at": g["changed_at"].isoformat(),
        }
        if g["op"] == "upsert":
            t = table_of(g["table"])
            row = conn.execute(select(t).where(t.c.id == g["row_id"])).mappings().first()
            if row is None:
                continue  # deleted since; its delete entry follows
            change["data"] = serialize_row(conn, spec, row)
        change["_order"] = (RANK[g["table"]], g["first"])
        changes.append(change)

    changes.sort(key=lambda c: c.pop("_order"))
    return changes, ids


def delete_outbox(conn, ids: list[int]) -> None:
    for i in range(0, len(ids), 500):
        conn.execute(delete(OUTBOX).where(OUTBOX.c.id.in_(ids[i:i + 500])))


# --------------------------------------------------
# APPLY (receiver side)
# --------------------------------------------------

def _local_is_newer(conn, table: str, local_id: int, incoming: datetime) -> bool:
    latest = conn.execute(
        select(func.max(OUTBOX.c.changed_at))
        .where(OUTBOX.c.table_name == table, OUTBOX.c.row_id == local_id)
    ).scalar()
    if latest is None:
        return False
    if settings.NODE_ROLE == "lan":
        return latest >= incoming   # ties go to the LAN server
    return latest > incoming


def _find_by_natural_key(conn, spec: TableSpec, data: dict) -> int | None:
    nk = spec.natural_key
    if not nk or data.get(nk) is None:
        return None
    t = table_of(spec.table)
    value = _decode_scalar(t.c[nk], data[nk])
    row = conn.execute(select(t.c.id).where(t.c[nk] == value)).first()
    return row[0] if row else None


def _apply_upsert(conn, spec: TableSpec, change: dict, final: bool, stats: dict) -> bool:
    """Returns False if the change must wait for rows later in the batch."""
    t = table_of(spec.table)
    sid = change["sync_id"]
    changed_at = datetime.fromisoformat(change["changed_at"])

    local_id, exists = resolve(conn, spec.table, sid)
    if local_id is not None and not exists:
        stats["skipped"] += 1  # deleted here; deletes win
        return True
    if local_id is None:
        local_id = _find_by_natural_key(conn, spec, change["data"])
        if local_id is not None:
            add_map(conn, spec.table, local_id, sid)

    if local_id is not None and not (settings.NODE_ROLE == "cloud" and spec.direction == "up"):
        if _local_is_newer(conn, spec.table, local_id, changed_at):
            stats["skipped"] += 1
            return True

    values, unresolved = decode_row(conn, spec, change["data"])
    required_missing = [c for c in unresolved if not t.c[c].nullable]
    if unresolved and not final:
        if required_missing:
            return False
        # Write now without the missing links; the second pass fills them in.
        stats.setdefault("_retry", []).append(change)
    if unresolved and final:
        if required_missing:
            raise SyncError(
                f"{spec.table} {sid}: referenced rows missing for {', '.join(required_missing)}"
            )
        stats["warnings"].append(f"{spec.table} {sid}: unresolved {', '.join(unresolved)}")
    for c in unresolved:
        values.pop(c, None)

    try:
        if local_id is not None:
            if values:
                conn.execute(update(t).where(t.c.id == local_id).values(**values))
        else:
            res = conn.execute(insert(t).values(**values))
            local_id = res.inserted_primary_key[0]
            add_map(conn, spec.table, local_id, sid)
    except IntegrityError as e:
        # e.g. the same patient number issued on both nodes. Stop loudly
        # rather than merge or drop a record; shows up in /api/sync/status.
        raise SyncError(f"{spec.table} {sid}: {e.orig}") from e

    for col, template in spec.files.items():
        if template and values.get(col):
            local_path = template.format(id=local_id)
            if local_path != values[col]:
                conn.execute(update(t).where(t.c.id == local_id).values({col: local_path}))

    stats["applied"] += 1
    stats.setdefault("_touched", set()).add((spec.table, local_id))
    return True


def _apply_delete(conn, spec: TableSpec, change: dict, stats: dict) -> None:
    t = table_of(spec.table)
    local_id, exists = resolve(conn, spec.table, change["sync_id"])
    if local_id is None or not exists:
        return
    if _local_is_newer(conn, spec.table, local_id, datetime.fromisoformat(change["changed_at"])):
        stats["skipped"] += 1
        return
    nested = conn.begin_nested()
    try:
        conn.execute(delete(t).where(t.c.id == local_id))
        nested.commit()
        stats["deleted"] += 1
    except IntegrityError:
        nested.rollback()
        stats["warnings"].append(f"{spec.table} {change['sync_id']}: delete blocked by dependent rows")


def apply_incoming(db: Session, changes: list[dict]) -> dict:
    """
    Apply a batch from the other node inside the caller's transaction.
    The caller commits. Raises SyncError if the batch can't be applied as a whole.
    """
    stats = {"applied": 0, "deleted": 0, "skipped": 0, "warnings": []}
    db.info["sync_applying"] = True  # capture.py ignores writes made here
    try:
        conn = db.connection()
        ordered = []
        for c in changes:
            spec = spec_for(c.get("table", ""))
            if not spec:
                stats["warnings"].append(f"unknown table {c.get('table')}")
                continue
            if settings.NODE_ROLE == "lan" and spec.direction == "up":
                continue
            ordered.append((RANK[spec.table], spec, c))
        ordered.sort(key=lambda x: x[0])

        waiting = []
        for _, spec, c in ordered:
            if c["op"] == "delete":
                _apply_delete(conn, spec, c, stats)
            elif not _apply_upsert(conn, spec, c, final=False, stats=stats):
                waiting.append((spec, c))

        # Second pass: rows whose parents came later in the batch, and
        # links (e.g. test_requests.test_result_id) left empty in pass one.
        retry = stats.pop("_retry", [])
        for spec, c in waiting:
            _apply_upsert(conn, spec, c, final=True, stats=stats)
        for c in retry:
            stats["applied"] -= 1  # counted once already
            _apply_upsert(conn, spec_for(c["table"]), c, final=True, stats=stats)
        stats.pop("_retry", None)
    finally:
        db.info.pop("sync_applying", None)
    return stats


# SSDO index (patient timelines / disease history used by the portals) is
# derived data, rebuilt on each node rather than synced.
_REINDEX = {
    "patients": "index_patient_task",
    "test_requests": "index_request_task",
    "test_results": "index_result_task",
}


def reindex_jobs(stats: dict) -> list:
    """Call after the batch is committed: [(function, local_id), ...] to run."""
    from app.services.ssdo import tasks
    touched = stats.pop("_touched", set())
    return [(getattr(tasks, _REINDEX[t]), i) for t, i in sorted(touched) if t in _REINDEX]
