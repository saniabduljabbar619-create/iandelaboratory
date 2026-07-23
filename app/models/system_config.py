# -*- coding: utf-8 -*-
# app/models/system_config.py
from __future__ import annotations
from sqlalchemy import Column, Integer, String, Text, DateTime, func
from app.db.base import Base


class SystemConfig(Base):
    """
    Single-row-per-key configuration store.
    Drives first_run detection, SAS onboarding state, feature flags.
    """
    __tablename__ = "system_config"

    id = Column(Integer, primary_key=True)
    key = Column(String(100), unique=True, nullable=False, index=True)
    value = Column(Text, nullable=True)
    updated_at = Column(DateTime, server_default=func.now(), onupdate=func.now())