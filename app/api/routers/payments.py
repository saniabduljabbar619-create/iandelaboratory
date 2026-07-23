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
from app.schemas.payment import PaymentCreate, PaymentOut, PaymentReconcileOut
from app.services.payment_service import PaymentService
from fastapi.responses import FileResponse


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



@router.get("/reconcile", response_model=PaymentReconcileOut) # <-- Changed response_model
def reconcile_payments(
    start_date: datetime = Query(None),
    end_date: datetime = Query(None),
    branch_id: int = Query(None),
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    svc = PaymentService(db, current_user, requested_branch_id=branch_id)
    
    # 1. Get the raw rows
    rows = svc.reconcile(start_date=start_date, end_date=end_date)
    
    # 2. Get the summary totals
    summary = svc.reconcile_summary(start_date=start_date, end_date=end_date)

    # 3. Format the payments list
    payments_out = []
    for p in rows:
        d = PaymentOut.model_validate(p).model_dump()
        d["request_ids"] = PaymentService.parse_request_ids(p)
        payments_out.append(PaymentOut(**d))

    # 4. Return the combined object
    return {
        "payments": payments_out,
        "summary": summary
    }
    
    
@router.get("/cashier-summary")
def cashier_summary(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Today's snapshot for the logged-in cashier (isolation model)."""
    svc = PaymentService(db, current_user)
    return svc.cashier_today_summary()


@router.get("/cashier-report")
def cashier_report(
    start_date: datetime = Query(None),
    end_date: datetime = Query(None),
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Period financial report for the logged-in cashier (isolation model)."""
    svc = PaymentService(db, current_user)
    return svc.cashier_period_report(start_date=start_date, end_date=end_date)



@router.get("/{payment_id}/receipt")
def payment_receipt(
    payment_id: int,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Generate (or regenerate) the thermal receipt PDF for a payment."""
    from app.services.receipt_service import generate_receipt_pdf
    from app.models.payment import Payment
    payment = db.query(Payment).filter(Payment.id == payment_id).first()
    if not payment:
        from fastapi import HTTPException
        raise HTTPException(status_code=404, detail="Payment not found.")
    pdf_path = generate_receipt_pdf(db, payment)
    return FileResponse(
        path=str(pdf_path),
        media_type="application/pdf",
        filename=f"receipt_{payment_id}.pdf",
    )