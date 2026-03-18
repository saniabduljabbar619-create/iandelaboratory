# -*- coding: utf-8 -*-
from __future__ import annotations

from sqlalchemy import Column, Integer, String, DateTime, func, JSON, Index
from app.db.base import Base


class AuditLog(Base):
    __tablename__ = "audit_logs"

    id = Column(Integer, primary_key=True)

    actor_type = Column(String(50), nullable=False)   # "staff" | "portal"
    actor = Column(String(255), nullable=True)        # role/username/email etc
    action = Column(String(100), nullable=False)      # "status_change" | "portal_login" | "portal_download"
    entity = Column(String(100), nullable=True)       # "test_result"
    entity_id = Column(Integer, nullable=True)

    ip = Column(String(64), nullable=True)
    meta = Column(JSON, nullable=True)

    created_at = Column(DateTime, server_default=func.now(), nullable=False)


Index("ix_audit_action_time", AuditLog.action, AuditLog.created_at)
