# -*- coding: utf-8 -*-
# app/models/portal_auth.py
"""
Portal authentication attempt tracker.
Enforces PORTAL_MAX_FAILS and PORTAL_LOCK_MINUTES from settings.
"""
from __future__ import annotations

from sqlalchemy import Column, Integer, String, DateTime, func
from app.db.base import Base


class PortalAuthAttempt(Base):
    __tablename__ = "portal_auth_attempts"

    id            = Column(Integer, primary_key=True)
    phone         = Column(String(20), nullable=False, index=True)
    ip_address    = Column(String(50), nullable=True)
    attempt_count = Column(Integer, nullable=False, default=0)
    locked_until  = Column(DateTime, nullable=True)
    last_attempt  = Column(DateTime, nullable=True)
    created_at    = Column(DateTime, server_default=func.now(), nullable=False)
    updated_at    = Column(DateTime, server_default=func.now(),
                          onupdate=func.now(), nullable=False)