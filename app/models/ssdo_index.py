# -*- coding: utf-8 -*-
# app/models/ssdo_index.py
from __future__ import annotations
from sqlalchemy import (
    Column, Integer, String, DateTime, Boolean,
    JSON, ForeignKey, func, Index
)
from sqlalchemy.orm import relationship
from app.db.base import Base


class SSDOIndex(Base):
    """
    SSDO classification index.
    Every record that enters the system gets an entry here
    at write time via a background task.
    """
    __tablename__ = "ssdo_index"

    id = Column(Integer, primary_key=True)

    # What kind of record this is
    record_type = Column(String(50), nullable=False, index=True)
    # test_result | test_request | patient_profile | payment | report

    # The actual record this entry describes
    record_id = Column(Integer, nullable=False, index=True)

    # Who this data belongs to
    patient_id = Column(
        Integer, ForeignKey("patients.id"), nullable=True, index=True
    )

    # Clinical classification
    test_category = Column(String(100), nullable=True, index=True)
    # Haematology | Biochemistry | Microbiology | Serology | Blood Bank

    disease_tags = Column(JSON, nullable=True)
    # ["malaria", "anemia", "hepatitis_b"]

    severity_flag = Column(String(20), nullable=True, index=True)
    # normal | borderline | critical | unknown

    # Where this record sits on the patient timeline
    temporal_position = Column(DateTime, nullable=True, index=True)

    # Groups records from the same visit together
    grouped_with = Column(String(36), nullable=True)

    # Portal visibility control
    portal_visible = Column(Boolean, default=True, nullable=False)

    # SAS processing state
    ai_processed = Column(Boolean, default=False, nullable=False, index=True)
    ai_summary = Column(JSON, nullable=True)
    # SAS understanding of this record

    branch_id = Column(Integer, ForeignKey("branches.id"), nullable=True)
    indexed_at = Column(DateTime, server_default=func.now(), nullable=False)
    updated_at = Column(
        DateTime, server_default=func.now(), onupdate=func.now()
    )

    patient = relationship("Patient")
    branch = relationship("Branch")


Index("ix_ssdo_patient_type", SSDOIndex.patient_id, SSDOIndex.record_type)
Index("ix_ssdo_category_severity", SSDOIndex.test_category, SSDOIndex.severity_flag)