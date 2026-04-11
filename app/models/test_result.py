# -*- coding: utf-8 -*-
# app/ models/test_result.py
from __future__ import annotations
import uuid  # ✅ Add this line right at the top
import enum
from sqlalchemy import Column, Integer, DateTime, func, ForeignKey, Enum, JSON, String, Index
from sqlalchemy.orm import relationship
from sqlalchemy import ForeignKey
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base


class ResultStatus(str, enum.Enum):
    draft = "draft"
    in_progress = "in_progress"
    pending_review = "pending_review"
    approved = "approved"
    released = "released"


class TestResult(Base):
    __tablename__ = "test_results"

    id = Column(Integer, primary_key=True)

    sync_id = Column(String(36), unique=True, index=True, default=lambda: str(uuid.uuid4()))

    patient_id = Column(Integer, ForeignKey("patients.id"), nullable=False, index=True)
    test_type_id = Column(Integer, ForeignKey("test_types.id"), nullable=False, index=True)
    template_id = Column(Integer, ForeignKey("test_templates.id"), nullable=True, index=True)

    status = Column(Enum(ResultStatus), default=ResultStatus.draft, nullable=False, index=True)

    # Snapshot copied from template at creation time (never changes)
    template_snapshot = Column(JSON, nullable=False)

    # User-entered values
    values = Column(JSON, nullable=False, default=lambda: {})
    flags = Column(JSON, nullable=False, default=lambda: {})

    # Optional notes / remarks
    notes = Column(String(500), nullable=True)

    created_at = Column(DateTime, server_default=func.now(), nullable=False)
    updated_at = Column(DateTime, server_default=func.now(), onupdate=func.now(), nullable=False)

    patient = relationship("Patient", lazy="joined")
    test_type = relationship("TestType", lazy="joined")
    template = relationship("TestTemplate", lazy="joined")
    branch = relationship("Branch", lazy="joined")
    branch_id: Mapped[int] = mapped_column(ForeignKey("branches.id"), nullable=False)
    pdf_path = Column(String(500), nullable=True)


Index("ix_results_patient_status", TestResult.patient_id, TestResult.status)
