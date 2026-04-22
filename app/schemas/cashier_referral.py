# -*- coding: utf-8 -*-
from pydantic import BaseModel, Field
from typing import List, Optional
from datetime import date

class PatientReferralEntry(BaseModel):
    full_name: str
    phone: str
    gender: Optional[str] = None
    dob: Optional[date] = None
    test_type_ids: List[int]
    sample_type: str = "Blood"

class ReferralFinancials(BaseModel):
    discount_percent: float = 0.0
    payment_method: str = "Cash"

class CashierReferralSyncRequest(BaseModel):
    facility_name: str
    facility_phone: str
    facility_address: Optional[str] = None
    clinician_name: str
    referrer_id: int
    patients: List[PatientReferralEntry]
    financials: ReferralFinancials
