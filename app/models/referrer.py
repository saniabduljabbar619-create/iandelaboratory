# -*- coding: utf-8 -*-
from __future__ import annotations

from sqlalchemy import Column, Integer, String, Numeric, Boolean, DateTime, func
from app.db.base import Base


class Referrer(Base):
    __tablename__ = "referrers"

    id = Column(Integer, primary_key=True)

    name = Column(String(255), nullable=False)
    email = Column(String(255), nullable=True, unique=True, index=True)
    phone = Column(String(20), nullable=False, index=True)

    credit_limit = Column(Numeric(12, 2), nullable=False, default=0)

    is_active = Column(Boolean, default=True)

    created_at = Column(DateTime, server_default=func.now(), nullable=False)