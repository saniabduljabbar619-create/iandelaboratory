# -*- coding: utf-8 -*-
from sqlalchemy.orm import Session
from sqlalchemy import func

from app.models.booking import Booking
from app.models.booking_item import BookingItem
from app.models.patient import Patient
from app.models.test_request import TestRequest
from fastapi import HTTPException

class BookingConversionService:

    @staticmethod
    def convert_patient(
        db: Session,
        booking_id: int,
        patient_name: str,
        branch_id: int,
        cashier_name: str
    ):

        # --------------------------------------
        # LOAD BOOKING
        # --------------------------------------

        booking = db.query(Booking).filter(
            Booking.id == booking_id
        ).first()

        if not booking:
            raise Exception("Booking not found")

        if booking.status == "converted":
            raise Exception("Booking already processed")

        if booking.status not in ["payment_verified", "approved_credit"]:
            raise Exception("Booking not ready for conversion")

        # --------------------------------------
        # FETCH ITEMS
        # --------------------------------------

        items = db.query(BookingItem).filter(
            BookingItem.booking_id == booking_id,
            BookingItem.patient_name == patient_name,
            BookingItem.converted == False
        ).all()

        # --------------------------------------
        # HANDLE EMPTY (ALREADY PROCESSED)
        # --------------------------------------

        if not items:

            remaining = db.query(BookingItem).filter(
                BookingItem.booking_id == booking_id,
                BookingItem.converted == False
            ).count()

            if remaining == 0:
                booking.status = "converted"
                db.commit()

            raise Exception("Nothing to convert")

        # --------------------------------------
        # RESOLVE PATIENT
        # --------------------------------------

        first = items[0]

        patient = db.query(Patient).filter(
            Patient.phone == first.patient_phone
        ).first()

        if not patient:
            from app.utils.patient_no_generator import generate_patient_no

            patient = Patient(
                patient_no=generate_patient_no(db),
                full_name=first.patient_name,
                phone=first.patient_phone,
                date_of_birth=first.dob,
                gender=first.gender,
                branch_id=branch_id
            )

            db.add(patient)
            db.flush()

        # --------------------------------------
        # CREATE TEST REQUESTS
        # --------------------------------------

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

        # --------------------------------------
        # FINALIZE BOOKING
        # --------------------------------------

        remaining = db.query(BookingItem).filter(
            BookingItem.booking_id == booking_id,
            BookingItem.converted == False
        ).count()

        if remaining == 0:
            booking.status = "converted"

        db.commit()

        return created_requests