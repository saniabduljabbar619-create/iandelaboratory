# app/api/routers/referrer.py
from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session
from sqlalchemy import func

from app.api.deps import get_db
from app.models.booking import Booking
from app.models.referrer import Referrer
from fastapi import HTTPException


router = APIRouter(prefix="/api/referrer", tags=["Referrer"])



@router.get("/dashboard")
def get_dashboard(referrer_id: int, db: Session = Depends(get_db)):
    # -----------------------------
    # TOTAL CREDIT
    # -----------------------------
    total_credit = (
        db.query(func.coalesce(func.sum(Booking.total_amount), 0))
        .filter(
            Booking.referrer_id == referrer_id,
            Booking.status == "approved_credit"
        )
        .scalar()
    )

    # -----------------------------
    # GROUPED BOOKINGS
    # -----------------------------
    grouped = (
        db.query(
            Booking.booking_code,
            func.sum(Booking.total_amount).label("booking_total"),
            func.count(Booking.id).label("patients_count"),
            func.max(Booking.created_at).label("created_at")
        )
        .filter(
            Booking.referrer_id == referrer_id,
            Booking.status == "approved_credit"
        )
        .group_by(Booking.booking_code)
        .order_by(func.max(Booking.created_at).desc())
        .all()
    )

    bookings = [
        {
            "booking_code": g.booking_code,
            "booking_total": float(g.booking_total),
            "patients_count": g.patients_count,
            "created_at": g.created_at
        }
        for g in grouped
    ]

    return {
        "total_credit": float(total_credit),
        "bookings": bookings
    }


@router.get("/booking/{booking_code}")
def get_booking_details(
    booking_code: str,
    referrer_id: int,
    db: Session = Depends(get_db)
):
    rows = (
        db.query(Booking)
        .filter(
            Booking.booking_code == booking_code,
            Booking.referrer_id == referrer_id,
            Booking.status == "approved_credit"
        )
        .order_by(Booking.created_at.desc())
        .all()
    )

    return [
        {
            "full_name": r.full_name,
            "phone": r.phone,
            "amount": float(r.total_amount),
            "created_at": r.created_at
        }
        for r in rows
    ]



@router.post("/login")
def referrer_login(payload: dict, db: Session = Depends(get_db)):
    email = payload.get("email")
    phone = payload.get("phone")

    if not phone:
        raise HTTPException(status_code=400, detail="Phone required")

    ref = (
        db.query(Referrer)
        .filter(
            Referrer.phone == phone,
            Referrer.is_active == True
        )
        .first()
    )

    if not ref:
        raise HTTPException(status_code=401, detail="Invalid credentials")

    return {
        "referrer_id": ref.id,
        "name": ref.name
    }



@router.get("/login-test")
def login_test(phone: str, db: Session = Depends(get_db)):
    return referrer_login({"phone": phone}, db)