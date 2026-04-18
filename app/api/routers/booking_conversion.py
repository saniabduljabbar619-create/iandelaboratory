# -*- coding: utf-8 -*-
# app/api/routes/booking_conversion.py

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.api.deps import get_db
from app.models.booking_item import BookingItem
from app.services.booking_conversion_service import BookingConversionService
from app.models.booking import Booking
router = APIRouter(prefix="/api/bookings", tags=["Bookings"])


@router.post("/{booking_id}/convert")
def convert_patient_request(
    booking_id: int,
    patient_name: str, # Keep this as str to match frontend
    branch_id: int,
    cashier_name: str,
    db: Session = Depends(get_db)
):
    try:
        booking = db.query(Booking).filter(Booking.id == booking_id).first()
        if not booking:
            raise HTTPException(status_code=404, detail="Booking not found")

        if booking.status not in ["payment_verified", "approved_credit"]:
            raise HTTPException(status_code=400, detail="Booking not ready for conversion")

        # 🔥 BRIDGE THE GAP 🔥
        # Find the patient_id associated with this name in this booking
        item = db.query(BookingItem).filter(
            BookingItem.booking_id == booking_id,
            BookingItem.patient_name == patient_name
        ).first()

        if not item:
            raise HTTPException(status_code=404, detail="Patient not found in this booking")

        # Call the service using the ID it now requires
        requests = BookingConversionService.convert_patient(
            db=db,
            booking_id=booking_id,
            patient_id=item.patient_id, # Use the ID from the item
            branch_id=branch_id,
            cashier_name=cashier_name
        )

        return {
            "status": "success",
            "message": "Requests created",
            "requests_created": len(requests)
        }
    except HTTPException: raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@router.get("/{booking_id}/patients")
def get_booking_patients(
    booking_id: int,
    db: Session = Depends(get_db),
):
    """
    Return patients inside a booking.
    Each patient may have multiple tests.
    """

    rows = (
        db.query(BookingItem)
        .filter(BookingItem.booking_id == booking_id)
        .all()
    )

    patients = {}

    for r in rows:

        key = f"{r.patient_name}_{r.patient_phone}"

        if key not in patients:
            patients[key] = {
                "patient_name": r.patient_name,
                "phone": r.patient_phone,
                "dob": r.dob,
                "gender": r.gender,
                "tests": []
            }

        patients[key]["tests"].append(
            r.test_name_snapshot
        )

    return list(patients.values())
