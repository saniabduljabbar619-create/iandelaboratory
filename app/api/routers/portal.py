# -*- coding: utf-8 -*-
# app/api/routers/portal.py — LabCore v2.0
from __future__ import annotations

from fastapi import APIRouter, Depends, Header, Request
from fastapi.responses import FileResponse
from sqlalchemy.orm import Session

from app.api.deps import get_db
from app.core.config import settings
from app.schemas.portal import PortalLogin, PortalTokenOut
from app.services.portal_service import PortalService
from app.services.audit_service import AuditService
from fastapi import HTTPException

router = APIRouter()


def _portal(db: Session) -> PortalService:
    return PortalService(db, secret=settings.PORTAL_SECRET)


def _get_patient_id(
    authorization: str | None,
    db: Session,
) -> int:
    if not authorization or not authorization.lower().startswith("bearer "):
        raise HTTPException(status_code=401, detail="Missing portal token.")
    token = authorization.split(" ", 1)[1].strip()
    return _portal(db).verify_token(token)


# --------------------------------------------------
# AUTH
# --------------------------------------------------

@router.post("/login")
def portal_login(
    payload: PortalLogin,
    request: Request,
    db: Session = Depends(get_db),
):
    """
    Patient portal login.
    Credentials: phone number + patient ID (patient_no).
    Returns a short-lived HMAC token valid for PORTAL_JWT_EXPIRES_MIN minutes.
    Brute-force protected: locks after PORTAL_MAX_FAILS consecutive failures.
    """
    ip = request.client.host if request.client else None

    try:
        token_data = _portal(db).login(payload.phone, payload.patient_no, ip=ip)

        AuditService(db).log(
            actor_type="portal",
            actor=f"phone:{payload.phone}",
            action="portal_login",
            entity="portal",
            entity_id=None,
            ip=ip,
            meta={"success": True},
        )

        return token_data

    except HTTPException as exc:
        if exc.status_code != 429:
            AuditService(db).log(
                actor_type="portal",
                actor=f"phone:{payload.phone}",
                action="portal_login",
                entity="portal",
                entity_id=None,
                ip=ip,
                meta={"success": False, "reason": exc.detail},
            )
        raise


# --------------------------------------------------
# PATIENT PROFILE
# --------------------------------------------------

@router.get("/me")
def portal_me(
    authorization: str | None = Header(default=None),
    db: Session = Depends(get_db),
):
    """Patient's own profile — name, patient_no, disease history summary."""
    patient_id = _get_patient_id(authorization, db)
    return _portal(db).get_patient_profile(patient_id)


# --------------------------------------------------
# RESULTS
# --------------------------------------------------

@router.get("/results")
def portal_list_results(
    authorization: str | None = Header(default=None),
    db: Session = Depends(get_db),
):
    """
    List all released results for the logged-in patient.
    Each result includes: test name, date, disease tags, severity,
    SAS-assisted flag, and download URL.
    """
    patient_id = _get_patient_id(authorization, db)
    return _portal(db).list_released_results(patient_id)


@router.get("/results/{result_id}/pdf")
def portal_download_pdf(
    result_id: int,
    request: Request,
    authorization: str | None = Header(default=None),
    db: Session = Depends(get_db),
):
    """
    Download a released result as a professional PDF.
    Includes QR code, barcode, flag highlighting, and lab branding.
    """
    ip = request.client.host if request.client else None
    patient_id = _get_patient_id(authorization, db)

    ps = _portal(db)
    result = ps.get_released_result(patient_id, result_id)

    # v2.0 — use the professionalized PDF service
    from app.services.result_pdf_service import generate_result_pdf
    pdf_path = generate_result_pdf(result, source="portal")

    AuditService(db).log(
        actor_type="portal",
        actor=f"patient_id:{patient_id}",
        action="portal_download",
        entity="test_result",
        entity_id=result.id,
        ip=ip,
        meta={"patient_id": patient_id},
    )

    return FileResponse(
        path=str(pdf_path),
        media_type="application/pdf",
        filename=f"result_{result.id}.pdf",
    )


# --------------------------------------------------
# QR VERIFICATION
# --------------------------------------------------

@router.get("/verify/{sync_id}")
def verify_result(
    sync_id: str,
    db: Session = Depends(get_db),
):
    """
    Public endpoint — no auth required.
    Called when someone scans the QR code on a printed result PDF.
    Returns the result summary if it's released and authentic.
    """
    return _portal(db).verify_result_by_sync_id(sync_id)