# -*- coding: utf-8 -*-
# app/models/patient.py
from __future__ import annotations
import uuid
from sqlalchemy import Column, Integer, String, Date, DateTime, Boolean, func, Index
from app.db.base import Base
from sqlalchemy import ForeignKey
from sqlalchemy.orm import Mapped, mapped_column


class Patient(Base):
    __tablename__ = "patients"

    id = Column(Integer, primary_key=True)
    sync_id = Column(String(36), unique=True, index=True, default=lambda: str(uuid.uuid4()))

    patient_no = Column(String(50), unique=True, nullable=False, index=True)
    full_name = Column(String(255), nullable=False, index=True)
    phone = Column(String(30), nullable=False, index=True)

    date_of_birth = Column(Date, nullable=True)
    gender = Column(String(20), nullable=True)
    blood_group = Column(String(10), nullable=True)   # A+/A-/B+/B-/AB+/AB-/O+/O- (confirmed at cross-match)
    address = Column(String(255), nullable=True)
    email = Column(String(255), nullable=True)

    # v2.0 — structured age (for neonates/infants who lack a DOB)
    age_value = Column(Integer, nullable=True)
    age_unit = Column(String(10), nullable=True)   # years | months | weeks | days

    # v2.0 — portal access
    portal_code = Column(String(255), nullable=True)      # hashed
    portal_enabled = Column(Boolean, default=True, nullable=False, server_default="1")

    # v2.0 — referrer link (nullable; usually set at booking)
    referrer_id = Column(Integer, nullable=True)

    created_at = Column(DateTime, server_default=func.now(), nullable=False)
    updated_at = Column(DateTime, server_default=func.now(), onupdate=func.now(), nullable=False)
    branch_id: Mapped[int] = mapped_column(ForeignKey("branches.id"), nullable=False)


Index("ix_patients_phone_patient_no", Patient.phone, Patient.patient_no)