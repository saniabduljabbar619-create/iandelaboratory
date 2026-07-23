# -*- coding: utf-8 -*-
# app/models/blood_bank.py
from __future__ import annotations
import uuid
from sqlalchemy import (
    Column, Integer, String, Date, DateTime,
    Boolean, ForeignKey, func, Index
)
from sqlalchemy.orm import relationship
from app.db.base import Base


class BloodDonor(Base):
    __tablename__ = "blood_donors"

    id = Column(Integer, primary_key=True)
    sync_id = Column(
        String(36), unique=True, index=True,
        default=lambda: str(uuid.uuid4())
    )
    full_name = Column(String(255), nullable=False, index=True)
    phone = Column(String(30), nullable=False, index=True)
    date_of_birth = Column(Date, nullable=True)
    gender = Column(String(20), nullable=True)

    blood_group = Column(String(10), nullable=False, index=True)
    # A+ | A- | B+ | B- | AB+ | AB- | O+ | O-

    genotype = Column(String(10), nullable=True)
    # AA | AS | SS | AC

    address = Column(String(255), nullable=True)
    last_donation_date = Column(Date, nullable=True)
    donation_count = Column(Integer, default=0, nullable=False)

    is_eligible = Column(Boolean, default=True, nullable=False)
    ineligibility_reason = Column(String(255), nullable=True)

    branch_id = Column(Integer, ForeignKey("branches.id"), nullable=False)
    created_at = Column(DateTime, server_default=func.now())
    updated_at = Column(DateTime, server_default=func.now(), onupdate=func.now())

    branch = relationship("Branch")


class BloodInventory(Base):
    __tablename__ = "blood_inventory"

    id = Column(Integer, primary_key=True)
    blood_group = Column(String(10), nullable=False, index=True)

    component = Column(String(50), nullable=False)
    # Whole Blood | Plasma | Platelets | Packed RBC

    units_available = Column(Integer, default=0, nullable=False)
    units_reserved = Column(Integer, default=0, nullable=False)

    collection_date = Column(Date, nullable=False)
    expiry_date = Column(Date, nullable=False, index=True)

    donor_id = Column(Integer, ForeignKey("blood_donors.id"), nullable=True)
    batch_no = Column(String(50), nullable=True, index=True)

    status = Column(String(30), default="available", nullable=False, index=True)
    # available | reserved | used | expired | discarded

    branch_id = Column(Integer, ForeignKey("branches.id"), nullable=False)
    created_at = Column(DateTime, server_default=func.now())
    updated_at = Column(DateTime, server_default=func.now(), onupdate=func.now())

    donor = relationship("BloodDonor")
    branch = relationship("Branch")


class CrossMatch(Base):
    __tablename__ = "cross_matches"

    id = Column(Integer, primary_key=True)
    sync_id = Column(
        String(36), unique=True, index=True,
        default=lambda: str(uuid.uuid4())
    )
    patient_id = Column(
        Integer, ForeignKey("patients.id"), nullable=False, index=True
    )
    inventory_id = Column(
        Integer, ForeignKey("blood_inventory.id"), nullable=False
    )
    requested_by = Column(String(120), nullable=True)

    result = Column(String(30), nullable=True)
    # compatible | incompatible | pending

    compatibility_notes = Column(String(500), nullable=True)
    performed_by = Column(String(120), nullable=True)
    performed_at = Column(DateTime, nullable=True)

    branch_id = Column(Integer, ForeignKey("branches.id"), nullable=False)
    created_at = Column(DateTime, server_default=func.now())

    patient = relationship("Patient")
    inventory = relationship("BloodInventory")
    branch = relationship("Branch")


Index("ix_blood_inventory_group_status", BloodInventory.blood_group, BloodInventory.status)