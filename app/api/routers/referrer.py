# app/api/routers/referrer.py
from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session
from sqlalchemy import func
from app.services.referrer_service import ReferrerService
from app.api.deps import get_db
from app.models.booking import Booking
from app.models.referrer import Referrer
from fastapi import HTTPException

from app.core.dependencies import get_db, get_current_user

router = APIRouter(prefix="/api/referrer", tags=["Referrer"])



@router.get("/dashboard")
def get_dashboard(referrer_id: int, db: Session = Depends(get_db)):
    # 🔥 ALIGNMENT: Use ReferrerService directly to ensure shared logic
    return ReferrerService.get_dashboard(db, referrer_id)
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
    # 🔥 ALIGNMENT: Ensures drill-down matches dashboard totals
    return ReferrerService.get_booking_details(db, booking_code, referrer_id)
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



# --- REFERRAL BATCH SYNC (New Smart Integration) ---

# --- REFERRAL BATCH SYNC (New Smart Integration) ---
@router.post("/sync-batch")
def sync_referral_batch(
    payload: dict, 
    db: Session = Depends(get_db),
    current_user=Depends(get_current_user)
):
    """
    Core synchronization endpoint for the Referral Wizard.
    Receives grouped patients, sample types, and tests to bridge 
    with stable clinical tables and the new parallel ledger.
    """
    from app.services.referrer_service import ReferrerService

    try:
        # Pass current_user to the service to satisfy the required argument
        batch_record = ReferrerService.create_referral_batch_sync(db, payload, current_user)
        
        return {
            "status": "success",
            "message": "Referral batch successfully synchronized and dispatched to lab.",
            "batch_uid": batch_record.batch_uid
        }
    except Exception as e:
        # Rollback is already handled inside the Service
        raise HTTPException(
            status_code=500,
            detail=f"Batch synchronization failed: {str(e)}"
        )

# --- ACTIVE BATCHES ---
@router.get("/active-batches")
def get_active_referral_batches(
    referrer_id: int | None = None,
    db: Session = Depends(get_db)
):
    """
    Retrieves all non-completed referral batches. 
    Filterable by referrer_id for specific hospital dashboards.
    """
    from app.models.referral_batch import ReferralBatch

    query = db.query(ReferralBatch).filter(ReferralBatch.status != "Completed")
    
    if referrer_id:
        query = query.filter(ReferralBatch.referrer_id == referrer_id)
        
    return query.order_by(ReferralBatch.created_at.desc()).all()

# --- CREATE REFERRER ---
@router.post("/create")
def create_referrer_profile(
    payload: dict,
    db: Session = Depends(get_db),
    current_user=Depends(get_current_user)
):
    """
    Endpoint to register a new Hospital or Doctor profile
    """
    from app.services.referrer_service import ReferrerService

    name = payload.get("name")
    phone = payload.get("phone")
    email = payload.get("email")
    credit_limit = payload.get("credit_limit", 0)

    if not name or not phone:
        raise HTTPException(status_code=400, detail="Name and Phone are required")

    return ReferrerService.create_referrer(
        db=db,
        name=name,
        phone=phone,
        email=email,
        credit_limit=credit_limit
    )

# --- LIST REFERRERS ---
@router.get("/list")
def list_referrers(db: Session = Depends(get_db)):
    """
    Helper to fetch all active referrers for your dropdown selector
    """
    return db.query(Referrer).filter(Referrer.is_active == True).all()
