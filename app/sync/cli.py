# -*- coding: utf-8 -*-
# app/sync/cli.py
"""
Sync commands for the LAN server PC. Run from the project folder:

  python -m app.sync.cli init-lan    once, right after restoring the cloud copy
  python -m app.sync.cli status      queue size, last success, last error
  python -m app.sync.cli run-once    sync now (pull, renumber, push) and print the result
"""
from __future__ import annotations

import json
import sys

from sqlalchemy import delete

from app.core.config import settings
from app.db.init_db import init_db
from app.db.session import SessionLocal
from app.sync import engine as sync
from app.sync import state


def init_lan() -> None:
    """
    The restored copy carries the cloud's own sync queue and status, which
    mean nothing here. Clear them. The id map is kept: it is identical on
    both sides at this point, which is exactly what we want.
    """
    if settings.NODE_ROLE != "lan":
        sys.exit("Refusing: NODE_ROLE must be 'lan' in this server's .env")
    init_db()  # creates the sync tables if the copy predates them
    db = SessionLocal()
    try:
        conn = db.connection()
        conn.execute(delete(sync.OUTBOX))
        state.clear_all(conn)
        db.commit()
    finally:
        db.close()
    print("LAN copy ready for sync.")


def status() -> None:
    db = SessionLocal()
    try:
        conn = db.connection()
        print(json.dumps({
            "role": settings.NODE_ROLE,
            "sync_enabled": settings.SYNC_ENABLED,
            "cloud_url": settings.SYNC_CLOUD_URL,
            "pending_changes": sync.pending_count(conn),
            "online": state.get(conn, "online"),
            "last_ok_at": state.get(conn, "last_ok_at"),
            "last_error": state.get(conn, "last_error"),
            "last_error_at": state.get(conn, "last_error_at"),
        }, indent=2))
    finally:
        db.close()


def run_once() -> None:
    if not (settings.SYNC_ENABLED and settings.NODE_ROLE == "lan"):
        sys.exit("Set NODE_ROLE=lan and SYNC_ENABLED=true in .env first")
    from app.sync import capture, agent
    capture.install()
    try:
        print(json.dumps(agent.run_once(), indent=2))
    except agent.CloudUnreachable as e:
        sys.exit(f"Cloud unreachable - working offline; changes stay queued. ({e})")
    except sync.SyncError as e:
        sys.exit(f"Sync failed: {e}")


COMMANDS = {"init-lan": init_lan, "status": status, "run-once": run_once}

if __name__ == "__main__":
    if len(sys.argv) != 2 or sys.argv[1] not in COMMANDS:
        sys.exit(f"usage: python -m app.sync.cli [{' | '.join(COMMANDS)}]")
    COMMANDS[sys.argv[1]]()
