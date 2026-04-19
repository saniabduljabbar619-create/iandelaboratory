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
    patient_id: int,     # 🔥 We only need the ID now
    branch_id: int,
    cashier_name: str,
    db: Session = Depends(get_db)
):
    try:
        # 1. Validate Booking
        booking = db.query(Booking).filter(Booking.id == booking_id).first()
        if not booking:
            raise HTTPException(status_code=404, detail="Booking not found")

        if booking.status not in ["payment_verified", "approved_credit"]:
            raise HTTPException(status_code=400, detail="Booking not ready for conversion")

        # 2. 🔥 CLEAN LOOKUP (No more 'patient_name' or 'clean_name' needed)
        # We find the item using the ID provided by the frontend
        item = db.query(BookingItem).filter(
            BookingItem.booking_id == booking_id,
            BookingItem.patient_id == patient_id
        ).first()

        # If not found by patient_id, fallback to row ID (just in case)
        if not item:
            item = db.query(BookingItem).filter(
                BookingItem.booking_id == booking_id,
                BookingItem.id == patient_id
            ).first()

        if not item:
            raise HTTPException(status_code=404, detail="Patient record not found for this booking")

        # 3. Call the service
        requests = BookingConversionService.convert_patient(
            db=db,
            booking_id=booking_id,
            patient_id=item.patient_id if item.patient_id else item.id, 
            branch_id=branch_id,
            cashier_name=cashier_name
        )

        return {
            "status": "success",
            "message": f"Successfully converted {len(requests)} tests for {item.patient_name}",
            "requests_created": len(requests)
        }

    except HTTPException: 
        raise
    except Exception as e:
        print(f"CONVERSION ERROR: {str(e)}") 
        raise HTTPException(status_code=500, detail=str(e))

@router.get("/{booking_id}/patients")
def get_booking_patients(booking_id: int, db: Session = Depends(get_db)):
    rows = db.query(BookingItem).filter(BookingItem.booking_id == booking_id).all()
    patients = {}

    for r in rows:
        key = f"{r.patient_name}_{r.patient_phone}"

        if key not in patients:
            # Guarantee an ID is sent to the frontend
            effective_id = r.patient_id if r.patient_id is not None else r.id

            patients[key] = {
                "id": effective_id, 
                "patient_name": r.patient_name,
                "phone": r.patient_phone,
                "dob": r.dob,
                "gender": r.gender,
                "tests": []
            }

        patients[key]["tests"].append(r.test_name_snapshot)

    return list(patients.values())
