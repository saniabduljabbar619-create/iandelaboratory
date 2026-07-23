# -*- coding: utf-8 -*-
# app/api/routers/referrer.py — LabCore v2.0 Modernized Referrer API
from __future__ import annotations

from typing import Optional

from fastapi import APIRouter, HTTPException, Depends, Query, UploadFile, File
from fastapi.responses import FileResponse
from sqlalchemy.orm import Session
from sqlalchemy import or_
from pydantic import BaseModel

from app.api.deps import get_db, get_current_user_claims
from app.services.referrer_service import ReferrerService
from app.services.referrer_profile_service import ReferrerProfileService

router = APIRouter(prefix="/api/referrer", tags=["referrer"])


# --------------------------------------------------
# SCHEMAS
# --------------------------------------------------

class ReferrerCreate(BaseModel):
    name: str
    phone: str
    email: Optional[str] = None
    credit_limit: float = 0
    organization_type: Optional[str] = None
    address: Optional[str] = None
    contact_person: Optional[str] = None
    license_no: Optional[str] = None
    discount_percent: float = 0


class ReferrerUpdate(BaseModel):
    name: Optional[str] = None
    email: Optional[str] = None
    phone: Optional[str] = None
    organization_type: Optional[str] = None
    address: Optional[str] = None
    contact_person: Optional[str] = None
    license_no: Optional[str] = None
    discount_percent: Optional[float] = None
    notes: Optional[str] = None
    credit_limit: Optional[float] = None


class SASQueryRequest(BaseModel):
    question: str


# --------------------------------------------------
# REFERRER MANAGEMENT
# --------------------------------------------------

@router.post("")
def create_referrer(
    payload: ReferrerCreate,
    db: Session = Depends(get_db),
    claims: dict = Depends(get_current_user_claims),
):
    """Register a new referrer (clinic, hospital, doctor, etc.)."""
    ref = ReferrerService.create_referrer(
        db=db,
        name=payload.name,
        phone=payload.phone,
        email=payload.email,
        credit_limit=payload.credit_limit,
    )
    # Apply extended fields
    if payload.organization_type:
        ref.organization_type = payload.organization_type
    if payload.address:
        ref.address = payload.address
    if payload.contact_person:
        ref.contact_person = payload.contact_person
    if payload.license_no:
        ref.license_no = payload.license_no
    ref.discount_percent = payload.discount_percent

    # Portal login credential — same pattern as patient portal codes
    from app.core.security import hash_password
    import secrets, string
    alphabet = "ABCDEFGHJKLMNPQRSTUVWXYZ23456789"  # no look-alikes
    portal_code_plain = "".join(secrets.choice(alphabet) for _ in range(6))
    ref.portal_code = hash_password(portal_code_plain)

    db.commit()
    db.refresh(ref)

    svc = ReferrerProfileService(db)
    profile = svc.get_profile(ref.id)
    profile["portal_code_plain"] = portal_code_plain  # shown once, for the cashier to relay
    return profile

@router.post("/{referrer_id}/reset-code")
def reset_portal_code(
    referrer_id: int,
    db: Session = Depends(get_db),
    claims: dict = Depends(get_current_user_claims),
):
    """Generate a new portal access code for a referrer (old one becomes invalid)."""
    from app.models.referrer import Referrer
    from app.core.security import hash_password
    import secrets

    ref = db.query(Referrer).filter(Referrer.id == referrer_id).first()
    if not ref:
        raise HTTPException(status_code=404, detail="Referrer not found")

    alphabet = "ABCDEFGHJKLMNPQRSTUVWXYZ23456789"
    portal_code_plain = "".join(secrets.choice(alphabet) for _ in range(6))
    ref.portal_code = hash_password(portal_code_plain)
    db.commit()

    return {"message": "Access code reset", "portal_code_plain": portal_code_plain}

@router.get("")
def list_referrers(
    q: Optional[str] = Query(default=None),
    active_only: bool = Query(default=True),
    db: Session = Depends(get_db),
    claims: dict = Depends(get_current_user_claims),
):
    """List all referrers (for the desktop Referrers screen)."""
    from app.models.referrer import Referrer
    query = db.query(Referrer)
    if active_only:
        query = query.filter(Referrer.is_active == True)
    if q and q.strip():
        s = f"%{q.strip()}%"
        query = query.filter(
            or_(Referrer.name.ilike(s), Referrer.phone.ilike(s), Referrer.email.ilike(s))
        )
    refs = query.order_by(Referrer.name.asc()).limit(200).all()
    return [
        {
            "id": r.id,
            "name": r.name,
            "phone": r.phone,
            "email": r.email,
            "organization_type": r.organization_type,
            "discount_percent": float(r.discount_percent or 0),
            "is_active": r.is_active,
        }
        for r in refs
    ]


@router.get("/{referrer_id}/profile")
def get_profile(
    referrer_id: int,
    db: Session = Depends(get_db),
    claims: dict = Depends(get_current_user_claims),
):
    """Full referrer profile with stats, avatar, and financial summary."""
    svc = ReferrerProfileService(db)
    return svc.get_profile(referrer_id)


@router.patch("/{referrer_id}/profile")
def update_profile(
    referrer_id: int,
    payload: ReferrerUpdate,
    db: Session = Depends(get_db),
    claims: dict = Depends(get_current_user_claims),
):
    """Update referrer profile fields."""
    svc = ReferrerProfileService(db)
    return svc.update_profile(referrer_id, payload.model_dump(exclude_none=True))


@router.post("/{referrer_id}/avatar")
def upload_avatar(
    referrer_id: int,
    file: UploadFile = File(...),
    db: Session = Depends(get_db),
    claims: dict = Depends(get_current_user_claims),
):
    """Upload a profile picture / DP for the referrer."""
    svc = ReferrerProfileService(db)
    return svc.upload_avatar(referrer_id, file)


# --------------------------------------------------
# PATIENT LIST + RESULTS
# --------------------------------------------------

@router.get("/{referrer_id}/patients")
def get_referred_patients(
    referrer_id: int,
    limit: int = Query(default=50, le=200),
    offset: int = Query(default=0),
    db: Session = Depends(get_db),
    claims: dict = Depends(get_current_user_claims),
):
    """
    Unified list of ALL patients referred by this referrer.
    Includes each patient's test results and SSDO disease tags.
    Sources: Booking flow + ReferralBatch flow combined.
    """
    svc = ReferrerProfileService(db)
    return svc.get_referred_patients(referrer_id, limit=limit, offset=offset)


@router.get("/{referrer_id}/patients/{patient_id}/results/{result_id}/download")
def download_result(
    referrer_id: int,
    patient_id: int,
    result_id: int,
    db: Session = Depends(get_db),
    claims: dict = Depends(get_current_user_claims),
):
    """
    Download a specific patient result PDF.
    Validates that the patient was referred by this referrer before serving.
    """
    svc = ReferrerProfileService(db)
    pdf_path = svc.download_patient_result(referrer_id, patient_id, result_id)
    return FileResponse(
        path=str(pdf_path),
        media_type="application/pdf",
        filename=f"result_{result_id}_patient_{patient_id}.pdf",
    )


# --------------------------------------------------
# BATCH HISTORY
# --------------------------------------------------

@router.get("/{referrer_id}/batches")
def get_batch_history(
    referrer_id: int,
    limit: int = Query(default=20),
    db: Session = Depends(get_db),
    claims: dict = Depends(get_current_user_claims),
):
    """Group booking / batch history for this referrer."""
    svc = ReferrerProfileService(db)
    return svc.get_batch_history(referrer_id, limit=limit)


# --------------------------------------------------
# SSDO INSIGHTS
# --------------------------------------------------

@router.get("/{referrer_id}/insights")
def get_ssdo_insights(
    referrer_id: int,
    db: Session = Depends(get_db),
    claims: dict = Depends(get_current_user_claims),
):
    """
    SSDO-powered population intelligence for this referrer.
    Shows disease frequency, severity distribution, and test category
    breakdown across ALL patients this referrer has sent to the lab.
    Useful for clinics monitoring their referred patient population.
    """
    svc = ReferrerProfileService(db)
    return svc.get_ssdo_insights(referrer_id)


# --------------------------------------------------
# SAS POPULATION QUERY
# --------------------------------------------------

@router.post("/{referrer_id}/sas-query")
def sas_query(
    referrer_id: int,
    payload: SASQueryRequest,
    db: Session = Depends(get_db),
    claims: dict = Depends(get_current_user_claims),
):
    """
    Ask SAS a question about this referrer's patient population.
    Powered by SSDO aggregated data — no patient PII involved.
    Example: 'What is the most common disease pattern among
    patients from this clinic over the past month?'
    """
    svc = ReferrerProfileService(db)
    insights = svc.get_ssdo_insights(referrer_id)
    ref_profile = svc.get_profile(referrer_id)

    from app.services.sas.core import SASCore
    core = SASCore(db)
    return core.query_lab(
        question=payload.question,
        branch_id=None,
    )


# --------------------------------------------------
# LEGACY — kept for backward compatibility
# --------------------------------------------------

@router.get("/dashboard")
def get_dashboard(
    referrer_id: int,
    db: Session = Depends(get_db),
):
    """Legacy dashboard endpoint — kept for backward compatibility."""
    return ReferrerService.get_dashboard(db, referrer_id)


@router.get("/booking/{booking_code}")
def get_booking_details(
    booking_code: str,
    referrer_id: int,
    db: Session = Depends(get_db),
):
    """Legacy booking detail endpoint — kept for backward compatibility."""
    return ReferrerService.get_booking_details(db, booking_code, referrer_id)