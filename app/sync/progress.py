# -*- coding: utf-8 -*-
# app/sync/progress.py
from __future__ import annotations

from app.core.config import settings
from app.sync import engine as sync
from app.sync import state


def progress_status(conn) -> dict:
    """
    Sync health plus a progress figure for the desktop apps' progress bar:
    of everything queued since the last time both sides were identical,
    how much has gone through (in either direction).
    """
    pending_up = sync.pending_count(conn)
    pending_down = int(state.get(conn, "pending_down", 0) or 0) if settings.NODE_ROLE == "lan" else 0
    synced = int(state.get(conn, "synced_since_idle", 0) or 0)
    pending = pending_up + pending_down
    total = synced + pending
    return {
        "enabled": True,
        "role": settings.NODE_ROLE,
        "cloud_url": settings.SYNC_CLOUD_URL if settings.NODE_ROLE == "lan" else None,
        "online": state.get(conn, "online"),
        "last_ok_at": state.get(conn, "last_ok_at"),
        "last_error": state.get(conn, "last_error"),
        "last_error_at": state.get(conn, "last_error_at"),
        "pending_changes": pending,
        "pending_up": pending_up,
        "pending_down": pending_down,
        "synced": synced,
        "total": total,
        "percent": 100 if total == 0 else int(synced * 100 / total),
    }
