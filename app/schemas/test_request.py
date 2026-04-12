# -*- coding: utf-8 -*-
# app/schemas/test_request.py

from __future__ import annotations

from pydantic import BaseModel, Field
from typing import Optional, Literal
from datetime import datetime

TestRequestStatus = Literal["pending", "paid", "accepted", "rejected", "fulfilled"]



class TestRequestCreate(BaseModel):
    patient_id: int = Field(..., ge=1)
    test_type_id: int = Field(..., ge=1)
    requested_by: Optional[str] = None
    requested_note: Optional[str] = None
    # ✅ Add these three so the service can "see" them during sync
    status: Optional[TestRequestStatus] = "pending"
    sync_id: str | None = Field(default=None, max_length=36)
    branch_id: int | None = None


class TestRequestStatusUpdate(BaseModel):
    status: TestRequestStatus
    test_result_id: Optional[int] = Field(default=None, ge=1)


class TestRequestOut(BaseModel):
    id: int
    sync_id: str | None 
    patient_id: int
    test_type_id: int
    status: TestRequestStatus

    requested_by: Optional[str] = None
    requested_note: Optional[str] = None

    accepted_at: Optional[datetime] = None
    fulfilled_at: Optional[datetime] = None
    test_result_id: Optional[int] = None

    created_at: datetime
    updated_at: datetime

    class Config:
        from_attributes = True
