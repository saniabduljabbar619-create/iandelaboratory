# -*- coding: utf-8 -*-
# app/ models/ patient.py
from __future__ import annotations
import uuid  # ✅ Add this line right at the top
from sqlalchemy import Column, Integer, String, Date, DateTime, func, Index
from app.db.base import Base
from sqlalchemy import ForeignKey
from sqlalchemy.orm import Mapped, mapped_column


class Patient(Base):
    __tablename__ = "patients"

    id = Column(Integer, primary_key=True)

    sync_id = Column(String(36), unique=True, index=True, default=lambda: str(uuid.uuid4()))

    # Patient ID Number (used as portal "password")
    patient_no = Column(String(50), unique=True, nullable=False, index=True)

    full_name = Column(String(255), nullable=False, index=True)
    phone = Column(String(30), nullable=False, index=True)

    date_of_birth = Column(Date, nullable=True)
    gender = Column(String(20), nullable=True)
    address = Column(String(255), nullable=True)

    created_at = Column(DateTime, server_default=func.now(), nullable=False)
    updated_at = Column(DateTime, server_default=func.now(), onupdate=func.now(), nullable=False)
    branch_id: Mapped[int] = mapped_column(ForeignKey("branches.id"), nullable=False)


Index("ix_patients_phone_patient_no", Patient.phone, Patient.patient_no)
