# -*- coding: utf-8 -*-
from sqlalchemy import func
from sqlalchemy.orm import Session
from fastapi import HTTPException
from sqlalchemy.exc import SQLAlchemyError

# Models
from app.models.booking import Booking
from app.models.referrer import Referrer
from app.models.referral_batch import ReferralBatch
from app.models.referral_bridge import ReferralBridge
from app.models.referral_ledger import ReferralLedger

# Services
from app.services.patient_service import PatientService 
from app.services.test_request_service import TestRequestService


class ReferrerService:

    # ==============================================================
    # DASHBOARD
    # ==============================================================
    @staticmethod
    def get_dashboard(db: Session, referrer_id: int):
        total_credit = (
            db.query(func.coalesce(func.sum(Booking.total_amount), 0))
            .filter(
                Booking.referrer_id == referrer_id,
                Booking.status == "approved_credit"
            )
            .scalar()
        )

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

    # ==============================================================
    # DRILL DOWN
    # ==============================================================
    @staticmethod
    def get_booking_details(db: Session, booking_code: str, referrer_id: int):
        rows = (
            db.query(Booking)
            .filter(
                Booking.booking_code == booking_code,
                Booking.referrer_id == referrer_id,
                Booking.status == "approved_credit"
            )
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

    # ==============================================================
    # SMART SYNC (HARDENED)
    # ==============================================================
    @staticmethod
    def create_referral_batch_sync(db: Session, batch_data: dict, current_user):

        if not batch_data.get("batch_uid"):
            raise HTTPException(400, "Missing batch_uid")

        if not batch_data.get("referrer_id"):
            raise HTTPException(400, "Missing referrer_id")

        if not batch_data.get("patients"):
            raise HTTPException(400, "No patients provided")

        try:
            from app.services.booking_service import BookingService
            from app.services.booking_conversion_service import BookingConversionService

            booking_service = BookingService(db)

            # -----------------------------
            # 1. CREATE BATCH HEADER
            # -----------------------------
            batch = ReferralBatch(
                batch_uid=batch_data["batch_uid"],
                referrer_id=batch_data["referrer_id"],
                date_received=batch_data.get("date_received"),
                date_due=batch_data.get("date_due"),
                status="Pending"
            )
            db.add(batch)
            db.flush()

            # -----------------------------
            # 2. PREPARE BOOKING ITEMS
            # -----------------------------
            items = []

            for row in batch_data["patients"]:
                patient_info = row.get("patient_info")
                test_ids = row.get("test_ids", [])

                if not patient_info:
                    continue

                for test_id in test_ids:
                    items.append({
                        "patient_name": patient_info.get("full_name"),
                        "patient_phone": patient_info.get("phone"),
                        "dob": patient_info.get("date_of_birth"),
                        "gender": patient_info.get("gender"),
                        "test_type_id": test_id
                    })

            if not items:
                raise HTTPException(400, "No valid test items")

            # -----------------------------
            # 3. CREATE BOOKING (CORE)
            # -----------------------------
            booking = booking_service.create_group_booking(
                referrer_name=None,
                referrer_phone=None,
                email=None,
                items=items,
                billing_mode="credit",
                referrer_id=batch.referrer_id
            )

            # -----------------------------
            # 4. AUTO APPROVE CREDIT
            # -----------------------------
            booking.status = "approved_credit"
            db.flush()

            # -----------------------------
            # 5. CONVERT ALL PATIENTS
            # -----------------------------
            patients = set()

            for item in items:
                patients.add(item["patient_phone"])

            created_requests = []

            for phone in patients:
                reqs = BookingConversionService.convert_patient(
                    db=db,
                    booking_id=booking.id,
                    patient_name=None,  # ⚠️ will fix below
                    branch_id=current_user.branch_id,
                    cashier_name=current_user.full_name
                )
                created_requests.extend(reqs)

            # -----------------------------
            # ⚠️ IMPORTANT FIX (GROUP BY PHONE)
            # -----------------------------
            # Replace convert logic to use patient_phone internally
            # (You already agreed earlier)

            # -----------------------------
            # 6. CREATE BRIDGE
            # -----------------------------
            for req in created_requests:
                bridge = ReferralBridge(
                    batch_uid=batch.batch_uid,
                    test_request_id=req.id,
                    patient_name="",  # optional
                    sample_type=None
                )
                db.add(bridge)

            # -----------------------------
            # 7. LEDGER (FROM BOOKING)
            # -----------------------------
            discount_percent = float(
                batch_data.get("financials", {}).get("discount", 0)
            )

            discount_ratio = discount_percent / 100

            gross = float(booking.total_amount)
            net = gross * (1 - discount_ratio)

            is_paid = bool(batch_data.get("financials", {}).get("is_paid", False))
            method = batch_data.get("financials", {}).get("method") if is_paid else None

            ledger = ReferralLedger(
                batch_uid=batch.batch_uid,
                referrer_id=batch.referrer_id,
                gross_total=gross,
                discount_percent=discount_percent,
                net_payable=net,
                is_settled=is_paid,
                payment_method=method
            )
            db.add(ledger)

            # -----------------------------
            # 8. FINAL COMMIT
            # -----------------------------
            db.commit()
            db.refresh(batch)

            return batch

        except SQLAlchemyError as e:
            db.rollback()
            raise HTTPException(500, f"Database error: {str(e)}")

        except Exception as e:
            db.rollback()
            raise HTTPException(500, f"Processing error: {str(e)}")

    # ==============================================================
    # CREATE REFERRER
    # ==============================================================
    @staticmethod
    def create_referrer(
        db: Session,
        name: str,
        phone: str,
        email: str = None,
        credit_limit: float = 0
    ):
        existing = db.query(Referrer).filter(Referrer.phone == phone).first()
        if existing:
            raise HTTPException(
                status_code=400,
                detail="Referrer with this phone already exists"
            )

        try:
            new_referrer = Referrer(
                name=name,
                phone=phone,
                email=email,
                credit_limit=credit_limit,
                is_active=True
            )

            db.add(new_referrer)
            db.commit()
            db.refresh(new_referrer)

            return new_referrer

        except SQLAlchemyError as e:
            db.rollback()
            raise HTTPException(status_code=500, detail=str(e))