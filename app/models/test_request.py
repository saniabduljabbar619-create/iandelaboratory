# -*- coding: utf-8 -*-
# app/models/test_request.py

from __future__ import annotations

import uuid  # ✅ Add this line right at the top
from sqlalchemy import ForeignKey
from sqlalchemy.orm import Mapped, mapped_column

from sqlalchemy import Column, Integer, DateTime, Enum, String, func
from app.db.base import Base


class TestRequest(Base):
    __tablename__ = "test_requests"

    id = Column(Integer, primary_key=True, autoincrement=True)

    sync_id = Column(String(36), unique=True, index=True, default=lambda: str(uuid.uuid4()))

    patient_id = Column(Integer, nullable=False, index=True)
    test_type_id = Column(Integer, nullable=False, index=True)

    status = Column(
        Enum("pending", "paid", "accepted", "rejected", "fulfilled", name="test_request_status"),
        nullable=False,
        index=True,
        server_default="pending",
    )

    requested_by = Column(String(120), nullable=True)
    requested_note = Column(String(500), nullable=True)

    accepted_at = Column(DateTime, nullable=True)
    fulfilled_at = Column(DateTime, nullable=True)

    test_result_id = Column(Integer, nullable=True, index=True)

    created_at = Column(DateTime, server_default=func.now(), nullable=False)
    updated_at = Column(DateTime, server_default=func.now(), onupdate=func.now(), nullable=False)
    branch_id: Mapped[int] = mapped_column(ForeignKey("branches.id"), nullable=False)

