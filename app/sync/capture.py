# -*- coding: utf-8 -*-
# app/sync/capture.py
"""
Records every ORM insert/update/delete on a synced table into sync_outbox,
inside the same transaction as the change itself — so a change is either
saved *and* queued for sync, or neither.

All writes in this codebase go through ORM objects; bulk query.update() /
query.delete() and raw SQL would bypass this hook.
"""
from __future__ import annotations

import logging

from sqlalchemy import event, inspect
from sqlalchemy.orm import Session

from app.core.config import settings
from app.sync import engine as sync
from app.sync.registry import spec_for

log = logging.getLogger("solunex.sync")
_installed = False


def _table_and_id(obj):
    state = inspect(obj)
    table = state.mapper.local_table.name
    ident = state.identity
    return table, (ident[0] if ident else getattr(obj, "id", None))


def _synced(table: str) -> bool:
    spec = spec_for(table)
    if not spec:
        return False
    # Cloud-side edits to LAN-authoritative tables are never sent down, so don't queue them.
    return not (settings.NODE_ROLE == "cloud" and spec.direction == "up")


def _after_flush(session: Session, flush_context) -> None:
    if session.info.get("sync_applying"):
        return
    conn = session.connection()

    for obj in list(session.new):
        table, row_id = _table_and_id(obj)
        if row_id is None or not _synced(table):
            continue
        sid = getattr(obj, "sync_id", None) or sync.new_sync_id()
        sync.add_map(conn, table, row_id, sid)
        sync.record_change(conn, table, row_id, sid, "upsert")

    for obj in list(session.dirty):
        if not session.is_modified(obj, include_collections=False):
            continue
        table, row_id = _table_and_id(obj)
        if row_id is None or not _synced(table):
            continue
        sync.record_change(conn, table, row_id, sync.local_sync_id(conn, table, row_id), "upsert")

    for obj in list(session.deleted):
        table, row_id = _table_and_id(obj)
        if row_id is None or not _synced(table):
            continue
        sync.record_change(conn, table, row_id, sync.local_sync_id(conn, table, row_id), "delete")


def install() -> None:
    """Hook every Session in the process. Safe to call more than once."""
    global _installed
    if _installed:
        return
    event.listen(Session, "after_flush", _after_flush)
    _installed = True
    log.info("sync capture installed (role=%s)", settings.NODE_ROLE)
