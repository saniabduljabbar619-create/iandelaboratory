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
from app.services.booking_service import BookingService


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
    # SMART BATCH SYNC (ATOMIC)
    # ==============================================================
    @staticmethod
    def create_referral_batch_sync(db: Session, batch_data: dict, current_user):
        """
        Atomic referral batch creation using BookingService as pricing source:
        - Batch header
        - Patients + Booking creation (pricing canonical)
        - Bridge linkage
        - Ledger entry
        """

        # -----------------------------
        # VALIDATION
        # -----------------------------
        if not batch_data.get("batch_uid"):
            raise HTTPException(400, "Missing batch_uid")
        if not batch_data.get("referrer_id"):
            raise HTTPException(400, "Missing referrer_id")
        if not batch_data.get("patients"):
            raise HTTPException(400, "No patients provided")
        if not batch_data.get("financials"):
            raise HTTPException(400, "Missing financials block")

        try:
            p_service = PatientService(db, current_user)
            booking_service = BookingService(db, current_user)

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

            computed_gross = 0.0
            booking_refs = []

            # -----------------------------
            # 2. PROCESS PATIENTS
            # -----------------------------
            for row in batch_data["patients"]:
                patient_info = row.get("patient_info")
                test_ids = row.get("test_ids", [])

                if not patient_info:
                    continue

                # Create patient
                new_patient = p_service.create(patient_info)

                # Create Booking for patient
                booking = booking_service.create_booking_for_referral(
                    patient_id=new_patient.id,
                    referrer_id=batch.referrer_id,
                    test_type_ids=test_ids,
                    batch_uid=batch.batch_uid
                )
                computed_gross += float(booking.total_amount)
                booking_refs.append(booking.booking_code)

                # Bridge linkage
                bridge = ReferralBridge(
                    batch_uid=batch.batch_uid,
                    booking_code=booking.booking_code,
                    patient_name=new_patient.full_name,
                    sample_type=row.get("sample_type")
                )
                db.add(bridge)

            # -----------------------------
            # 3. FINANCIAL COMPUTATION
            # -----------------------------
            discount_percent = float(batch_data["financials"].get("discount", 0))
            discount_ratio = discount_percent / 100
            computed_net = computed_gross * (1 - discount_ratio)
            is_paid = bool(batch_data["financials"].get("is_paid", False))
            method = batch_data["financials"].get("method") if is_paid else None

            # -----------------------------
            # 4. LEDGER ENTRY
            # -----------------------------
            ledger = ReferralLedger(
                batch_uid=batch.batch_uid,
                referrer_id=batch.referrer_id,
                gross_total=computed_gross,
                discount_percent=discount_percent,
                net_payable=computed_net,
                is_settled=is_paid,
                payment_method=method,
                booking_codes=",".join(booking_refs)
            )
            db.add(ledger)

            # -----------------------------
            # 5. COMMIT TRANSACTION
            # -----------------------------
            db.commit()
            db.refresh(batch)
            return batch

        except SQLAlchemyError as e:
            db.rollback()
            raise HTTPException(status_code=500, detail=f"Database error: {str(e)}")
        except Exception as e:
            db.rollback()
            raise HTTPException(status_code=500, detail=f"Processing error: {str(e)}")

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