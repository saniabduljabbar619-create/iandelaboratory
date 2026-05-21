# -*- coding: utf-8 -*-
# app/services/booking_conversion_service.py

from __future__ import annotations

from datetime import datetime
from sqlalchemy.orm import Session

from app.models.booking import Booking
from app.models.booking_item import BookingItem
from app.models.patient import Patient
from app.models.test_request import TestRequest


class BookingConversionService:

    # ── Mirrors PatientService._next_patient_no() ─────────────────────────────
    @staticmethod
    def _next_patient_no(db: Session) -> str:
        PREFIX = "IEL"
        PAD    = 4
        now    = datetime.now()
        year   = now.strftime("%y")
        year_prefix = f"{PREFIX}-{year}-"

        last = (
            db.query(Patient)
            .filter(Patient.patient_no.like(f"{year_prefix}%"))
            .order_by(Patient.patient_no.desc())
            .with_for_update()
            .first()
        )

        if not last:
            nxt = 4268 if year == "26" else 1
        else:
            try:
                nxt = int(last.patient_no.split("-")[-1]) + 1
            except (ValueError, IndexError):
                nxt = 1

        return f"{year_prefix}{nxt:0{PAD}d}"

    # ── Mirrors TestRequestService._next_request_no() ────────────────────────
    @staticmethod
    def _next_request_no(db: Session) -> str:
        PREFIX = "REQ"
        year   = datetime.now().strftime("%y")
        year_prefix = f"{PREFIX}-{year}-"

        last = (
            db.query(TestRequest)
            .filter(TestRequest.request_no.like(f"{year_prefix}%"))
            .order_by(TestRequest.request_no.desc())
            .with_for_update()
            .first()
        )

        if not last or not last.request_no:
            nxt = 1
        else:
            try:
                nxt = int(last.request_no.split("-")[-1]) + 1
            except (ValueError, IndexError):
                nxt = 1

        return f"{year_prefix}{nxt:04d}"

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

        # ── Step 2: All unconverted items for this patient ────────────────────
        items = db.query(BookingItem).filter(
            BookingItem.booking_id == booking_id,
            BookingItem.patient_name == anchor.patient_name,
            BookingItem.patient_phone == anchor.patient_phone,
            BookingItem.converted == False
        ).all()

        if not items:
            remaining = db.query(BookingItem).filter(
                BookingItem.booking_id == booking_id,
                BookingItem.converted == False
            ).count()
            if remaining == 0:
                booking.status = "converted"
                db.commit()
            raise Exception("Nothing to convert")

        # ── Step 3: Resolve Patient — auto-create with proper ID if needed ────

        patient = None

        # 3a. Try direct FK
        if anchor.patient_id:
            patient = db.query(Patient).filter(Patient.id == anchor.patient_id).first()

        # 3b. Phone lookup
        if not patient and anchor.patient_phone:
            patient = db.query(Patient).filter(Patient.phone == anchor.patient_phone).first()

        # 3c. Auto-create with a real sequential IEL-YY-NNNN patient number
        if not patient:
            patient = Patient(
                full_name=anchor.patient_name,
                phone=anchor.patient_phone,
                date_of_birth=anchor.dob,
                gender=anchor.gender,
                branch_id=branch_id,
                patient_no=BookingConversionService._next_patient_no(db),  # ← real ID
            )
            db.add(patient)
            db.flush()

        # ── Step 4: Backfill patient_id on items ─────────────────────────────
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
                branch_id=branch_id,
                request_no=BookingConversionService._next_request_no(db),
            )
            db.add(request)
            db.flush()  # flush each so next _next_request_no() sees it
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