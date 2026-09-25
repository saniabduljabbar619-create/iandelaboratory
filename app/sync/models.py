# -*- coding: utf-8 -*-
# app/sync/models.py
"""
Bookkeeping tables for LAN <-> cloud sync. They are new tables only;
no existing table is altered.

sync_outbox — one row per local change not yet delivered to the other node.
              The LAN deletes rows once the cloud accepts a push; the cloud
              deletes rows once the LAN confirms it has pulled them.
sync_map    — maps a row's local integer id to its global sync id. Ids
              differ between the two databases for rows created after the
              LAN copy was taken; the sync id is what both sides agree on.
sync_state  — small key/value store (pull cursor, last success, last error).
"""
from __future__ import annotations

from sqlalchemy import BigInteger, Column, DateTime, Index, Integer, String, Text, func
from sqlalchemy.dialects import mysql

from app.db.base import Base

# Microsecond timestamps so "newest edit wins" can tell close edits apart.
PreciseDateTime = DateTime().with_variant(mysql.DATETIME(fsp=6), "mysql")


class SyncOutbox(Base):
    __tablename__ = "sync_outbox"

    id = Column(BigInteger().with_variant(Integer, "sqlite"), primary_key=True, autoincrement=True)
    table_name = Column(String(64), nullable=False)
    row_id = Column(BigInteger, nullable=False)
    sync_id = Column(String(100), nullable=False)
    op = Column(String(10), nullable=False)  # upsert | delete
    changed_at = Column(PreciseDateTime, nullable=False)


Index("ix_sync_outbox_row", SyncOutbox.table_name, SyncOutbox.row_id)


class SyncMap(Base):
    __tablename__ = "sync_map"

    id = Column(BigInteger().with_variant(Integer, "sqlite"), primary_key=True, autoincrement=True)
    table_name = Column(String(64), nullable=False)
    local_id = Column(BigInteger, nullable=False)
    sync_id = Column(String(100), nullable=False, unique=True)


Index("ix_sync_map_local", SyncMap.table_name, SyncMap.local_id)


class SyncState(Base):
    __tablename__ = "sync_state"

    key = Column(String(100), primary_key=True)
    value = Column(Text, nullable=True)
    updated_at = Column(DateTime, server_default=func.now(), onupdate=func.now())
