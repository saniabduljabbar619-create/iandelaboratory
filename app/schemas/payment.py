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


class PaymentOut(BaseModel):
    id: int
    patient_id: int
    amount: float
    method: PaymentMethod
    status: PaymentStatus
    request_ids: List[int] = Field(default_factory=list)
    notes: Optional[str] = None
    created_at: datetime

    class Config:
        from_attributes = True
