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
    email: str | None = None
    # v2.0 — structured age
    age_value: int | None = None
    age_unit: str | None = None
    # v2.0 — portal enrollment
    portal_enabled: bool = True
    # v2.0 — referrer
    referrer_id: int | None = None
    # sync
    sync_id: str | None = Field(default=None, max_length=36)
    branch_id: int | None = None


class PatientUpdate(APIModel):
    full_name: str | None = None
    phone: str | None = None
    date_of_birth: date | None = None
    gender: str | None = None
    address: str | None = None
    email: str | None = None
    age_value: int | None = None
    age_unit: str | None = None
    referrer_id: int | None = None


class PatientOut(APIModel):
    id: int
    sync_id: str | None
    patient_no: str
    full_name: str
    phone: str
    date_of_birth: date | None
    gender: str | None
    address: str | None
    email: str | None = None
    age_value: int | None = None
    age_unit: str | None = None
    portal_enabled: bool = True
    referrer_id: int | None = None
    created_at: datetime
    updated_at: datetime
    # Returned ONCE on creation so the cashier can print/show the credential.
    # Never stored in plaintext; only echoed back at creation time.
    portal_code_plain: str | None = None