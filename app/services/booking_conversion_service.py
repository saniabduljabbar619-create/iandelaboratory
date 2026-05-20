# -*- coding: utf-8 -*-
# app/services/booking_conversion_service.py

from sqlalchemy.orm import Session

from app.models.booking import Booking
from app.models.booking_item import BookingItem
from app.models.patient import Patient
from app.models.test_request import TestRequest


class BookingConversionService:

    @staticmethod
    def convert_patient(
        db: Session,
        booking_id: int,
        patient_id: int,
        branch_id: int,
        cashier_name: str
    ):
        # ── Validate Booking ──────────────────────────────────────────────────
        booking = db.query(Booking).filter(Booking.id == booking_id).first()

        if not booking:
            raise Exception("Booking not found")

        if booking.status == "converted":
            raise Exception("Booking already processed")

        if booking.status not in ["payment_verified", "approved_credit"]:
            raise Exception("Booking not ready for conversion")

        # ── Step 1: Find anchor item (by patient_id FK or by row id) ─────────
        anchor = db.query(BookingItem).filter(
            BookingItem.booking_id == booking_id,
            (BookingItem.patient_id == patient_id) | (BookingItem.id == patient_id)
        ).first()

        if not anchor:
            raise Exception("Patient record not found in this booking")

        # ── Step 2: Fetch ALL unconverted items for this patient ──────────────
        # Group by name + phone since patient_id may be NULL for portal bookings
        items = db.query(BookingItem).filter(
            BookingItem.booking_id == booking_id,
            BookingItem.patient_name == anchor.patient_name,
            BookingItem.patient_phone == anchor.patient_phone,
            BookingItem.converted == False
        ).all()

        if not items:
            # Check if the whole booking is already done
            remaining = db.query(BookingItem).filter(
                BookingItem.booking_id == booking_id,
                BookingItem.converted == False
            ).count()

            if remaining == 0:
                booking.status = "converted"
                db.commit()

            raise Exception("Nothing to convert")

        # ── Step 3: Resolve Patient — auto-create if not found ───────────────

        patient = None

        # 3a. Try direct FK (pre-registered / cashier-registered patients)
        if anchor.patient_id:
            patient = db.query(Patient).filter(
                Patient.id == anchor.patient_id
            ).first()

        # 3b. Fall back to phone lookup (returning portal patients)
        if not patient and anchor.patient_phone:
            patient = db.query(Patient).filter(
                Patient.phone == anchor.patient_phone
            ).first()

        # 3c. Auto-create for first-time portal/walk-in patients
        if not patient:
            patient = Patient(
                full_name=anchor.patient_name,
                phone=anchor.patient_phone,
                dob=anchor.dob,
                gender=anchor.gender,
            )
            db.add(patient)
            db.flush()  # Materialise patient.id before use

        # ── Step 4: Backfill patient_id on all items for clean future lookups ─
        if not anchor.patient_id:
            for item in items:
                item.patient_id = patient.id

        # ── Step 5: Create TestRequest rows ──────────────────────────────────
        created_requests = []

        for item in items:
            request = TestRequest(
                patient_id=patient.id,
                test_type_id=item.test_type_id,
                status="paid",
                requested_by=cashier_name,
                branch_id=branch_id
            )
            db.add(request)
            item.converted = True
            created_requests.append(request)

        # ── Step 6: Close booking if fully converted ──────────────────────────
        remaining = db.query(BookingItem).filter(
            BookingItem.booking_id == booking_id,
            BookingItem.converted == False
        ).count()

        if remaining == 0:
            booking.status = "converted"

        db.commit()
        return created_requests