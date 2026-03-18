# -*- coding: utf-8 -*-
from __future__ import annotations

from fastapi import APIRouter, Depends, Request, HTTPException
from sqlalchemy.orm import Session

from app.api.deps import get_db
from app.services.audit_service import AuditService

router = APIRouter()


@router.get("/audit-test")
def audit_test(request: Request, db: Session = Depends(get_db)):
    ip = request.client.host if request.client else None

    # hard write
    AuditService(db).log(
        actor_type="system",
        actor="audit-test",
        action="audit_test",
        entity="audit_logs",
        entity_id=None,
        ip=ip,
        meta={"ok": True},
    )

    # confirm from same DB session
    count = db.execute("SELECT COUNT(*) FROM audit_logs").scalar()  # type: ignore
    return {"ok": True, "count_after": int(count)}
