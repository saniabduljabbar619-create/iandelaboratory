# -*- coding: utf-8 -*-
from __future__ import annotations

from fastapi import APIRouter, Depends, Header
from fastapi.responses import Response
from sqlalchemy.orm import Session

from fastapi import Request
from app.services.audit_service import AuditService


from app.api.deps import get_db
from app.core.config import settings
from app.schemas.portal import PortalLogin, PortalTokenOut, PortalResultItem
from app.services.portal_service import PortalService
from app.services.report_service import ReportService
from app.models.patient import Patient
from app.models.test_result import TestResult
from app.services.result_service import ResultService
from app.services.audit_service import AuditService
from fastapi import Request, HTTPException

router = APIRouter()


def _portal(db: Session) -> PortalService:
    return PortalService(db, secret=settings.PORTAL_SECRET)


@router.post("/login", response_model=PortalTokenOut)
def portal_login(payload: PortalLogin, request: Request, db: Session = Depends(get_db)):
    ip = request.client.host if request.client else None

    try:
        token_data = _portal(db).login(payload.phone, payload.patient_no)

        AuditService(db).log(
            actor_type="portal",
            actor=f"phone:{payload.phone}",
            action="portal_login",
            entity="portal",
            entity_id=None,
            ip=ip,
            meta={"success": True},
        )

        return PortalTokenOut(token=token_data["token"], expires_at=token_data["expires_at"])

    except HTTPException:
        AuditService(db).log(
            actor_type="portal",
            actor=f"phone:{payload.phone}",
            action="portal_login",
            entity="portal",
            entity_id=None,
            ip=ip,
            meta={"success": False},
        )
        raise


@router.get("/results", response_model=list[PortalResultItem])
def portal_list_results(
    authorization: str | None = Header(default=None),
    db: Session = Depends(get_db),
):
    if not authorization or not authorization.lower().startswith("bearer "):
        return []
    token = authorization.split(" ", 1)[1].strip()

    patient_id = _portal(db).verify_token(token)
    results: list[TestResult] = _portal(db).list_released_results(patient_id)

    return results


@router.get("/results/{result_id}/pdf")
def portal_download_pdf(
    result_id: int,
    request: Request,
    authorization: str | None = Header(default=None),
    db: Session = Depends(get_db),
):
    if not authorization or not authorization.lower().startswith("bearer "):
        raise HTTPException(status_code=401, detail="Unauthorized")

    ip = request.client.host if request.client else None
    token = authorization.split(" ", 1)[1].strip()

    ps = _portal(db)
    patient_id = ps.verify_token(token)
    result: TestResult = ps.get_released_result(patient_id, result_id)

    pdf_bytes = ReportService.generate_result_pdf(result)  # keep your function name

    AuditService(db).log(
        actor_type="portal",
        actor=f"patient_id:{patient_id}",
        action="portal_download",
        entity="test_result",
        entity_id=result.id,
        ip=ip,
        meta={"patient_id": patient_id},
    )

    return Response(
        content=pdf_bytes,
        media_type="application/pdf",
        headers={"Content-Disposition": f'attachment; filename="result_{result.id}.pdf"'},
    )
