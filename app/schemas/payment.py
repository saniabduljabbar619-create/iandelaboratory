# -*- coding: utf-8 -*-
# app/schemas/payment.py

from __future__ import annotations

from pydantic import BaseModel, Field
from typing import Optional, List, Literal
from datetime import datetime


PaymentMethod = Literal["Cash", "Transfer", "POS", "USSD"]
PaymentStatus = Literal["completed", "failed"]


class PaymentCreate(BaseModel):
    patient_id: int = Field(..., ge=1)
    amount: float = Field(..., gt=0)
    method: PaymentMethod
    request_ids: List[int] = Field(default_factory=list)
    notes: Optional[str] = None
    sync_id: str | None = Field(default=None, max_length=36)


class PaymentReconcileOut(BaseModel):
    payments: list[PaymentOut]
    summary: dict[str, float]  # e.g., {"Cash": 5000.0, "total": 5000.0}

class PaymentOut(BaseModel):
    id: int
    sync_id: str | None 
    patient_id: int
    amount: float
    method: PaymentMethod
    status: PaymentStatus
    request_ids: List[int] = Field(default_factory=list)
    notes: Optional[str] = None
    created_at: datetime

    class Config:
        from_attributes = True

