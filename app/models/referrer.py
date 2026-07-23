# -*- coding: utf-8 -*-
# app/models/referrer.py
from __future__ import annotations

from sqlalchemy import Column, Integer, String, Numeric, Boolean, DateTime, Text, func
from app.db.base import Base


class Referrer(Base):
    __tablename__ = "referrers"

    id = Column(Integer, primary_key=True)

    # Core identity
    name = Column(String(255), nullable=False)
    email = Column(String(255), nullable=True, unique=True, index=True)
    phone = Column(String(20),  nullable=False, index=True)

    # v2.0 — Profile enrichment
    avatar_path = Column(String(500), nullable=True)
    portal_code = Column(String(255), nullable=True)  # hashed access code, patient-portal pattern
    portal_code_expires_at = Column(DateTime, nullable=True)
    organization_type = Column(String(50), nullable=True)
    # clinic | hospital | doctor | lab | pharmacy | other

    address = Column(String(500), nullable=True)
    contact_person = Column(String(255), nullable=True)
    license_no = Column(String(100), nullable=True)
    discount_percent = Column(Numeric(5, 2), nullable=False, default=0.00, server_default="0.00")
    notes = Column(Text, nullable=True)

    # Financial
    credit_limit = Column(Numeric(12, 2), nullable=False, default=0)

    is_active = Column(Boolean, default=True)
    created_at = Column(DateTime, server_default=func.now(), nullable=False)
    updated_at = Column(DateTime, onupdate=func.now(), nullable=True)