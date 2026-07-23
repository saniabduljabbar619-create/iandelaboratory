# -*- coding: utf-8 -*-
# app/api/routers/blood_bank.py
from __future__ import annotations

from datetime import date
from typing import Optional

from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session
from pydantic import BaseModel

from app.api.deps import get_db, get_current_user_claims
from app.services.blood_bank_service import BloodBankService

router = APIRouter(prefix="/api/blood-bank", tags=["blood_bank"])


def _svc(db: Session, claims: dict) -> BloodBankService:
    branch_id = claims.get("branch_id") or 1
    return BloodBankService(db, branch_id=branch_id)


# --------------------------------------------------
# SCHEMAS
# --------------------------------------------------

class DonorCreate(BaseModel):
    full_name: str
    phone: str
    blood_group: str
    genotype: Optional[str] = None
    gender: Optional[str] = None
    date_of_birth: Optional[date] = None
    address: Optional[str] = None


class IneligibleRequest(BaseModel):
    reason: str


class DonationRequest(BaseModel):
    donation_date: date


class InventoryCreate(BaseModel):
    blood_group: str
    component: str
    units_available: int = 1
    collection_date: Optional[date] = None
    expiry_date: date
    donor_id: Optional[int] = None
    batch_no: Optional[str] = None


class CrossMatchRequest(BaseModel):
    patient_id: int
    inventory_id: int
    requested_by: Optional[str] = None
    patient_blood_group: Optional[str] = None   # tech-confirmed group at the bench


class CrossMatchResult(BaseModel):
    result: str
    performed_by: str
    notes: Optional[str] = None


# --------------------------------------------------
# DONOR ENDPOINTS
# --------------------------------------------------

@router.post("/donors")
def register_donor(
    payload: DonorCreate,
    db: Session = Depends(get_db),
    claims: dict = Depends(get_current_user_claims),
):
    """Register a new blood donor."""
    svc = _svc(db, claims)
    donor = svc.register_donor(payload.model_dump())
    return donor


@router.get("/donors")
def list_donors(
    blood_group: Optional[str] = Query(default=None),
    eligible_only: bool = Query(default=False),
    limit: int = Query(default=50),
    offset: int = Query(default=0),
    db: Session = Depends(get_db),
    claims: dict = Depends(get_current_user_claims),
):
    """List all donors, optionally filtered by blood group or eligibility."""
    svc = _svc(db, claims)
    donors, total = svc.list_donors(blood_group, eligible_only, limit, offset)
    return {"donors": donors, "total": total}


@router.get("/donors/{donor_id}")
def get_donor(
    donor_id: int,
    db: Session = Depends(get_db),
    claims: dict = Depends(get_current_user_claims),
):
    svc = _svc(db, claims)
    return svc.get_donor(donor_id)


@router.patch("/donors/{donor_id}/ineligible")
def mark_ineligible(
    donor_id: int,
    payload: IneligibleRequest,
    db: Session = Depends(get_db),
    claims: dict = Depends(get_current_user_claims),
):
    """Mark a donor as ineligible with a stated reason."""
    svc = _svc(db, claims)
    return svc.mark_ineligible(donor_id, payload.reason)


@router.post("/donors/{donor_id}/donate")
def record_donation(
    donor_id: int,
    payload: DonationRequest,
    db: Session = Depends(get_db),
    claims: dict = Depends(get_current_user_claims),
):
    """Record a donation event for a donor."""
    svc = _svc(db, claims)
    return svc.record_donation(donor_id, payload.donation_date)


# --------------------------------------------------
# INVENTORY ENDPOINTS
# --------------------------------------------------

@router.post("/inventory")
def add_inventory(
    payload: InventoryCreate,
    db: Session = Depends(get_db),
    claims: dict = Depends(get_current_user_claims),
):
    """Add a blood unit to inventory."""
    svc = _svc(db, claims)
    return svc.add_to_inventory(payload.model_dump())


@router.get("/inventory")
def list_inventory(
    blood_group: Optional[str] = Query(default=None),
    component: Optional[str] = Query(default=None),
    status: Optional[str] = Query(default=None),
    limit: int = Query(default=50),
    offset: int = Query(default=0),
    db: Session = Depends(get_db),
    claims: dict = Depends(get_current_user_claims),
):
    """List inventory, optionally filtered."""
    svc = _svc(db, claims)
    items, total = svc.list_inventory(blood_group, component, status, limit, offset)
    return {"inventory": items, "total": total}


@router.get("/inventory/summary")
def stock_summary(
    db: Session = Depends(get_db),
    claims: dict = Depends(get_current_user_claims),
):
    """Returns available units per blood group and component."""
    svc = _svc(db, claims)
    return svc.get_stock_summary()


@router.get("/inventory/{inventory_id}")
def get_inventory_item(
    inventory_id: int,
    db: Session = Depends(get_db),
    claims: dict = Depends(get_current_user_claims),
):
    svc = _svc(db, claims)
    return svc.get_inventory(inventory_id)


@router.post("/inventory/expire-stale")
def expire_stale(
    db: Session = Depends(get_db),
    claims: dict = Depends(get_current_user_claims),
):
    """Marks all past-expiry available units as expired."""
    svc = _svc(db, claims)
    count = svc.expire_stale_inventory()
    return {"message": f"{count} stale unit(s) marked as expired."}


# --------------------------------------------------
# CROSS MATCH ENDPOINTS
# --------------------------------------------------

@router.post("/cross-match")
def request_cross_match(
    payload: CrossMatchRequest,
    db: Session = Depends(get_db),
    claims: dict = Depends(get_current_user_claims),
):
    """Request a cross match — reserves the blood unit immediately."""
    svc = _svc(db, claims)
    return svc.request_cross_match(payload.model_dump())


@router.patch("/cross-match/{cross_match_id}/result")
def record_cross_match_result(
    cross_match_id: int,
    payload: CrossMatchResult,
    db: Session = Depends(get_db),
    claims: dict = Depends(get_current_user_claims),
):
    """Record the compatibility result. Incompatible releases the reservation."""
    svc = _svc(db, claims)
    return svc.record_cross_match_result(
        cross_match_id, payload.result, payload.performed_by, payload.notes
    )


@router.get("/cross-match")
def list_cross_matches(
    patient_id: Optional[int] = Query(default=None),
    result_filter: Optional[str] = Query(default=None),
    limit: int = Query(default=50),
    db: Session = Depends(get_db),
    claims: dict = Depends(get_current_user_claims),
):
    """List cross match records, optionally filtered by patient or result."""
    svc = _svc(db, claims)
    return svc.list_cross_matches(patient_id, result_filter, limit)