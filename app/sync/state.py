# -*- coding: utf-8 -*-
# app/sync/state.py
from __future__ import annotations

import json

from sqlalchemy import delete, insert, select, update

from app.sync.models import SyncState

STATE = SyncState.__table__


def get(conn, key: str, default=None):
    row = conn.execute(select(STATE.c.value).where(STATE.c.key == key)).first()
    if not row or row[0] is None:
        return default
    return json.loads(row[0])


def put(conn, key: str, value) -> None:
    raw = json.dumps(value)
    res = conn.execute(update(STATE).where(STATE.c.key == key).values(value=raw))
    if not res.rowcount:
        conn.execute(insert(STATE).values(key=key, value=raw))


def clear_all(conn) -> None:
    conn.execute(delete(STATE))
