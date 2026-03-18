# -*- coding: utf-8 -*-
from __future__ import annotations

from datetime import datetime
from typing import Optional

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
