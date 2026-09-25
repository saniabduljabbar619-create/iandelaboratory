# -*- coding: utf-8 -*-
# app/sync/agent.py
"""
Background sync worker on the LAN server PC.

Every SYNC_INTERVAL_SECONDS it:
  1. pulls changes made on the cloud (portal bookings, payment proofs,
     referrer activity) and applies them locally
  2. replaces temporary WEB- lab numbers with real ones
  3. pushes everything done in the lab since the last sync

When the internet is down each attempt fails fast and the lab carries on
against the local database; the queued changes go up once it's back.
Only one worker runs at a time even if uvicorn starts several processes.
"""
from __future__ import annotations

import logging
import threading
import time
from datetime import datetime

import requests
from sqlalchemy import select, text

from app.core.config import settings
from app.db.session import SessionLocal, engine
from app.sync import engine as sync
from app.sync import state
from app.sync.files import safe_upload_path
from app.sync.numbers import finalize_temp_lab_numbers
from app.sync.registry import spec_for

log = logging.getLogger("solunex.sync")

TIMEOUT = (5, 60)   # (connect, read) seconds
_wake = threading.Event()
_thread: threading.Thread | None = None


class CloudUnreachable(Exception):
    pass


def _post(path: str, **kwargs) -> dict:
    url = settings.SYNC_CLOUD_URL.rstrip("/") + path
    try:
        resp = requests.post(url, headers={"X-Sync-Token": settings.SYNC_TOKEN}, timeout=TIMEOUT, **kwargs)
    except requests.RequestException as e:
        raise CloudUnreachable(str(e)) from e
    if resp.status_code != 200:
        raise sync.SyncError(f"cloud {path} -> HTTP {resp.status_code}: {resp.text[:300]}")
    return resp.json()


# --------------------------------------------------
# FILES
# --------------------------------------------------

def _file_columns(change: dict):
    spec = spec_for(change["table"])
    if change["op"] != "upsert" or not spec or not spec.files:
        return []
    return [c for c in spec.files if (change.get("data") or {}).get(c)]


def _download_files(wanted: list[tuple[str, str, str]]) -> None:
    """
    Fetch files for rows that arrived from the cloud. Anything that can't be
    fetched now (connection dropped mid-way) is remembered and retried next cycle.
    """
    db = SessionLocal()
    try:
        conn = db.connection()
        wanted = state.get(conn, "file_retry", []) + [list(w) for w in wanted]
        failed = []
        for table, sync_id, col in wanted:
            local_id, exists = sync.resolve(conn, table, sync_id)
            if not exists:
                continue
            t = sync.table_of(table)
            path = safe_upload_path(conn.execute(select(t.c[col]).where(t.c.id == local_id)).scalar())
            if not path or path.exists():
                continue
            try:
                resp = requests.get(settings.SYNC_CLOUD_URL.rstrip("/") + "/api/sync/file",
                                    headers={"X-Sync-Token": settings.SYNC_TOKEN}, timeout=TIMEOUT,
                                    params={"table": table, "sync_id": sync_id, "column": col})
            except requests.RequestException:
                failed.append([table, sync_id, col])
                continue
            if resp.status_code == 200:
                path.parent.mkdir(parents=True, exist_ok=True)
                path.write_bytes(resp.content)
            elif resp.status_code == 404:
                log.warning("file %s is missing on the cloud too; skipping", path)
            else:
                failed.append([table, sync_id, col])
        state.put(conn, "file_retry", failed)
        db.commit()
    finally:
        db.close()


def _upload_files(db, changes: list[dict]) -> None:
    conn = db.connection()
    for ch in changes:
        for col in _file_columns(ch):
            path = safe_upload_path(ch["data"][col])
            if not path or not path.exists():
                continue
            with path.open("rb") as fh:
                _post("/api/sync/file",
                      data={"table": ch["table"], "sync_id": ch["sync_id"], "column": col},
                      files={"file": (path.name, fh)})
    db.commit()


# --------------------------------------------------
# ONE SYNC CYCLE
# --------------------------------------------------

def pull() -> int:
    total = 0
    while True:
        db = SessionLocal()
        try:
            ack = state.get(db.connection(), "pull_ack_ids", [])
            resp = _post("/api/sync/pull", json={"ack_ids": ack, "limit": settings.SYNC_BATCH_SIZE})
            changes = resp.get("changes", [])
            if changes:
                stats = sync.apply_incoming(db, changes)
                for w in stats["warnings"]:
                    log.warning("pull: %s", w)
            # Saved in the same transaction as the applied rows, and confirmed
            # to the cloud on the next request.
            state.put(db.connection(), "pull_ack_ids", resp.get("ids", []))
            db.commit()
        except Exception:
            db.rollback()
            raise
        finally:
            db.close()
        _download_files([(ch["table"], ch["sync_id"], col) for ch in changes for col in _file_columns(ch)])
        total += len(changes)
        if not resp.get("more"):
            return total


def push() -> int:
    total = 0
    while True:
        db = SessionLocal()
        try:
            changes, ids = sync.collect_outgoing(db.connection(), settings.SYNC_BATCH_SIZE)
            db.commit()  # keeps any seed mappings created while serializing
            if not ids:
                return total
            if changes:
                _post("/api/sync/push", json={"changes": changes})
                _upload_files(db, changes)
            sync.delete_outbox(db.connection(), ids)
            db.commit()
            total += len(changes)
        except Exception:
            db.rollback()
            raise
        finally:
            db.close()


def run_once() -> dict:
    """Pull, renumber, push. Records the outcome in sync_state for /api/sync/status."""
    result = {"pulled": 0, "renumbered": 0, "pushed": 0}
    now = datetime.utcnow().isoformat()
    try:
        result["pulled"] = pull()
        db = SessionLocal()
        try:
            result["renumbered"] = finalize_temp_lab_numbers(db)
        finally:
            db.close()
        result["pushed"] = push()
        _record(online=True, last_ok_at=now, last_error=None, last_error_at=None)
    except CloudUnreachable as e:
        _record(online=False, last_error=f"cloud unreachable: {e}", last_error_at=now)
        raise
    except Exception as e:
        _record(online=True, last_error=str(e)[:500], last_error_at=now)
        raise
    return result


def _record(**values) -> None:
    db = SessionLocal()
    try:
        conn = db.connection()
        for k, v in values.items():
            state.put(conn, k, v)
        db.commit()
    except Exception:
        db.rollback()
        log.exception("could not record sync status")
    finally:
        db.close()


# --------------------------------------------------
# BACKGROUND THREAD
# --------------------------------------------------

def _hold_single_runner_lock():
    """MySQL named lock so only one uvicorn worker runs the agent."""
    if engine.dialect.name != "mysql":
        return object()
    conn = engine.connect()
    if conn.execute(text("SELECT GET_LOCK('solunex_sync_agent', 0)")).scalar() == 1:
        return conn  # lock lives as long as this connection stays open
    conn.close()
    return None


def _loop() -> None:
    lock = None
    while lock is None:
        try:
            lock = _hold_single_runner_lock()
        except Exception:
            log.exception("sync lock")
        if lock is None:
            time.sleep(60)

    log.info("sync agent running -> %s every %ss", settings.SYNC_CLOUD_URL, settings.SYNC_INTERVAL_SECONDS)
    was_online = None
    while True:
        try:
            result = run_once()
            if was_online is False:
                log.info("cloud reachable again")
            was_online = True
            if result["pulled"] or result["pushed"] or result["renumbered"]:
                log.info("sync: %s", result)
        except CloudUnreachable as e:
            if was_online is not False:
                log.warning("cloud unreachable, working offline: %s", e)
            was_online = False
        except Exception:
            log.exception("sync cycle failed")
        _wake.wait(settings.SYNC_INTERVAL_SECONDS)
        _wake.clear()


def wake() -> None:
    """Run the next cycle now instead of waiting for the interval."""
    _wake.set()


def start() -> None:
    global _thread
    if _thread is not None:
        return
    if not (settings.SYNC_CLOUD_URL and settings.SYNC_TOKEN):
        log.warning("LAN sync enabled but SYNC_CLOUD_URL / SYNC_TOKEN not set; agent not started")
        return
    _thread = threading.Thread(target=_loop, name="sync-agent", daemon=True)
    _thread.start()
