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
        from app.services.booking_service import BookingService
        from app.services.booking_conversion_service import BookingConversionService
        from app.models.test_request import TestRequest
        
        p_service = PatientService(db, current_user)
        booking_service = BookingService(db)

        try:
            # 1. CREATE BATCH HEADER
            batch = ReferralBatch(
                batch_uid=batch_data["batch_uid"],
                referrer_id=batch_data["referrer_id"],
                date_received=batch_data.get("date_received"),
                date_due=batch_data.get("date_due") or batch_data.get("date_received"),
                status="Pending"
            )
            db.add(batch)

            computed_gross = 0.0
            booking_refs = []

            # 2. PROCESS PATIENTS & SILENT CONVERSION
            for row in batch_data["patients"]:
                patient_info = row.get("patient_info")
                test_ids = row.get("test_ids", [])
                if not patient_info: continue

                # A. Create Clinical Patient
                from app.schemas.patient import PatientCreate
                new_patient = p_service.create(PatientCreate(**patient_info))

                # B. Build Booking Items
                booking_items = [
                    {"test_type_id": tid, "patient_name": new_patient.full_name, "patient_phone": new_patient.phone}
                    for tid in test_ids
                ]

                # C. Create the Booking (Financial Record)
                booking = booking_service.create_booking(
                    "referral",
                    batch_data.get("referrer_name"),
                    new_patient.phone,
                    None,
                    booking_items,
                    billing_mode="credit",
                    referrer_id=batch.referrer_id
                )
                
                # Critical: Set status so conversion service accepts it
                booking.status = "approved_credit"
                db.flush() # Sync state to DB to get booking.id

                # ------------------------------------------------------
                # D. SILENT CONVERSION (THE "BYPASS")
                # ------------------------------------------------------
                # This populates the Lab Worklist instantly
                # app/services/referrer_service.py

# ... inside create_referral_batch_sync patient loop ...

                # ------------------------------------------------------
                # SILENT CONVERSION (PHASE 2)
                # ------------------------------------------------------
                try:
                    from app.services.booking_conversion_service import BookingConversionService
                    
                    # Using current_user.username (from your User model)
                    created_requests = BookingConversionService.convert_patient(
                        db=db,
                        booking_id=booking.id,
                        patient_name=new_patient.full_name,
                        branch_id=current_user.branch_id or 1, # Fallback to 1 if user has no branch
                        cashier_name=f"{current_user.username} (Auto-Sync)"
                    )
                    
                    # ------------------------------------------------------
                    # BRIDGE LINKAGE
                    # ------------------------------------------------------
                    # We link the newly created clinical TestRequests to the Batch
                    for req in created_requests:
                        db.add(ReferralBridge(
                            batch_uid=batch.batch_uid,
                            test_request_id=req.id,
                            patient_name=new_patient.full_name,
                            sample_type=row.get("sample_type")
                        ))
                        
                except Exception as conv_err:
                    # Log the specific error but don't break the whole batch sync
                    print(f"SILENT CONVERSION ERROR: {str(conv_err)}")
                    raise HTTPException(status_code=500, detail=f"Conversion failed: {str(conv_err)}")


            # 3. FINANCIALS & LEDGER (Same as before)
            discount_percent = float(batch_data["financials"].get("discount", 0))
            computed_net = computed_gross * (1 - (discount_percent / 100))
            
            ledger = ReferralLedger(
                batch_uid=batch.batch_uid,
                referrer_id=batch.referrer_id,
                gross_total=computed_gross,
                discount_percent=discount_percent,
                net_payable=computed_net,
                is_settled=bool(batch_data["financials"].get("is_paid", False)),
                payment_method=batch_data["financials"].get("method")
            )
            db.add(ledger)

            db.commit()
            db.refresh(batch)
            return batch

        except Exception as e:
            db.rollback()
            raise HTTPException(status_code=500, detail=f"Bypass Sync Failed: {str(e)}")

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