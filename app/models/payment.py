# -*- coding: utf-8 -*-
# app/models/payment.py

from __future__ import annotations
import uuid  # ✅ Add this line right at the top
from sqlalchemy import Column, Integer, DateTime, Enum, String, Float, func
from sqlalchemy import ForeignKey
from sqlalchemy.orm import Mapped, mapped_column
from sqlalchemy.orm import Mapped, relationship # Ensure relationship is imported

from app.db.base import Base


class Payment(Base):
    __tablename__ = "payments"

    id = Column(Integer, primary_key=True, autoincrement=True)

    sync_id = Column(String(36), unique=True, index=True, default=lambda: str(uuid.uuid4()))

    patient_id = Column(Integer, nullable=True, index=True)

    # For now we store request ids as comma string: "12,15,20"
    # (minimal, no JSON dependency)
    request_ids_csv = Column(String(500), nullable=True)

    amount = Column(Float, nullable=False)

    method = Column(
        Enum("Cash", "Transfer", "POS", "USSD", name="payment_method"),
        nullable=False,
        server_default="Cash",
    )

    status = Column(
        Enum("completed", "failed", name="payment_status"),
        nullable=False,
        server_default="completed",
        index=True,
    )

    notes = Column(String(500), nullable=True)

    # NEW: Track the cashier/admin who handled the money
    created_by_id: Mapped[int] = mapped_column(ForeignKey("users.id"), nullable=True)
    
    created_at = Column(DateTime, server_default=func.now(), nullable=False)
    branch_id: Mapped[int] = mapped_column(ForeignKey("branches.id"), nullable=False)


    # ADD THESE RELATIONSHIPS
    created_by = relationship("User") 
    branch = relationship("Branch")

