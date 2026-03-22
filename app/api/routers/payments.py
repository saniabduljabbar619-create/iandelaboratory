# -*- coding: utf-8 -*-
# app/api/routers/payments.py

from __future__ import annotations

from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session
from datetime import datetime
from app.api.deps import get_db
from app.core.dependencies import get_current_user
from app.models.user import User
from app.models.booking import Booking
from app.schemas.payment import PaymentCreate, PaymentOut
from app.services.payment_service import PaymentService

router = APIRouter()


@router.get("", response_model=list[PaymentOut])
def list_payments(
    patient_id: int = Query(..., ge=1),
    limit: int = Query(default=200, ge=1, le=500),
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    svc = PaymentService(db, current_user)
    rows = svc.list(patient_id=patient_id, limit=limit)

    out = []
    for p in rows:
        d = PaymentOut.model_validate(p).model_dump()
        d["request_ids"] = PaymentService.parse_request_ids(p)
        out.append(PaymentOut(**d))
    return out


@router.post("", response_model=PaymentOut)
def create_payment(
    payload: PaymentCreate,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    svc = PaymentService(db, current_user)
    p = svc.create(payload)

    d = PaymentOut.model_validate(p).model_dump()
    d["request_ids"] = PaymentService.parse_request_ids(p)

    return PaymentOut(**d)


@router.get("/verified-bookings")
def get_verified_bookings(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):

    rows = (
        db.query(Booking)
        .filter(
            Booking.status.in_(["payment_verified", "approved_credit"]),
            Booking.status != "converted"
        )
        .order_by(Booking.created_at.desc())
        .all()
    )

    out = []

    for b in rows:
        out.append(
            {
                "id": b.id,
                "booking_code": b.booking_code,
                "referrer_name": b.referrer_name,
                "referrer_phone": b.referrer_phone,
                "email": b.email,
                "status": b.status,
                "created_at": b.created_at,
            }
        )

    return out



@router.get("/reconcile", response_model=PaymentReconcileOut)
def reconcile_payments(
    start_date: datetime = Query(None),
    end_date: datetime = Query(None),
    branch_id: int = Query(None),
    current_user: User = Depends(require_roles("admin", "super_admin")),
    db: Session = Depends(get_db),
):
    if current_user.role != "super_admin":
        branch_id = None

    svc = PaymentService(db, current_user, requested_branch_id=branch_id)

    rows = svc.reconcile(start_date=start_date, end_date=end_date)
    summary = svc.reconcile_summary(start_date=start_date, end_date=end_date)

    return {
        "payments": [serialize_payment(p) for p in rows],
        "summary": summary
    }
