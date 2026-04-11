# -*- coding: utf-8 -*-

from __future__ import annotations

from datetime import date, datetime
from pydantic import Field
from app.schemas.common import APIModel


class PatientCreate(APIModel):
    patient_no: str | None = Field(default=None, max_length=50)
    full_name: str = Field(..., min_length=1, max_length=255)
    phone: str = Field(..., min_length=3, max_length=30)
    date_of_birth: date | None = None
    gender: str | None = None
    address: str | None = None
    # ✅ Added for Sync Engine: When the local Mini Server pushes an offline 
    # patient up to Aiven, it needs to be able to send the UUID it already generated.
    sync_id: str | None = Field(default=None, max_length=36)
    # ✅ Add this so the Sync Engine can pass the branch link!
    branch_id: int | None = None

class PatientUpdate(APIModel):
    full_name: str | None = None
    phone: str | None = None
    date_of_birth: date | None = None
    gender: str | None = None
    address: str | None = None


class PatientOut(APIModel):
    id: int
    # ✅ Exposes the UUID so your Desktop App and Sync Engine can read it
    sync_id: str | None
    patient_no: str
    full_name: str
    phone: str
    date_of_birth: date | None
    gender: str | None
    address: str | None
    created_at: datetime
    updated_at: datetime
