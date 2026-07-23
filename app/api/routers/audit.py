# -*- coding: utf-8 -*-
from __future__ import annotations

from datetime import datetime
from typing import Optional
from app.core.dependencies import get_current_user
from fastapi import APIRouter, Depends, Header, HTTPException, Query
from sqlalchemy.orm import Session
from sqlalchemy import desc

from app.api.deps import get_db
from app.models.audit_log import AuditLog
from app.schemas.audit import AuditLogOut

router = APIRouter()


def require_admin(role: str | None) -> None:
    r = (role or "").lower().strip()
    if r not in {"admin", "supervisor"}:
        raise HTTPException(status_code=403, detail="Forbidden")


@router.get("", response_model=list[AuditLogOut])
def list_audits(
    db: Session = Depends(get_db),
    x_role: str | None = Header(default=None, alias="X-Role"),
    action: Optional[str] = Query(default=None),
    actor_type: Optional[str] = Query(default=None),
    actor: Optional[str] = Query(default=None),
    entity: Optional[str] = Query(default=None),
    entity_id: Optional[int] = Query(default=None),
    limit: int = Query(default=50, ge=1, le=200),
):
    require_admin(x_role)

    q = db.query(AuditLog)

    if action:
        q = q.filter(AuditLog.action == action)
    if actor_type:
        q = q.filter(AuditLog.actor_type == actor_type)
    if actor:
        q = q.filter(AuditLog.actor.like(f"%{actor}%"))
    if entity:
        q = q.filter(AuditLog.entity == entity)
    if entity_id is not None:
        q = q.filter(AuditLog.entity_id == entity_id)

    rows = q.order_by(desc(AuditLog.id)).limit(limit).all()
    return rows


from pydantic import BaseModel

class GuardrailLogIn(BaseModel):
    patient_id: int
    test_type_id: int | None = None
    result_id: int | None = None
    guardrail: str
    severity: str
    message: str
    acknowledged: bool = True
    reason: str | None = None

@router.post("/guardrail")
def log_guardrail(
    payload: GuardrailLogIn,
    current_user=Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Log a guardrail fire + acknowledgment to the audit trail."""
    from app.services.audit_service import AuditService
    AuditService(db).log(
        actor_type="staff",
        actor=getattr(current_user, "username", "unknown"),
        action="guardrail_" + payload.guardrail,
        entity="test_result",
        entity_id=payload.result_id,
        meta={
            "patient_id": payload.patient_id,
            "test_type_id": payload.test_type_id,
            "severity": payload.severity,
            "message": payload.message,
            "acknowledged": payload.acknowledged,
            "reason": payload.reason,
        },
    )
    return {"logged": True}