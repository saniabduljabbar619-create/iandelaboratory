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
        # 1. TOTAL CREDIT (Commerce Layer remains the same)
        total_credit = (
            db.query(func.coalesce(func.sum(Booking.total_amount), 0))
            .filter(
                Booking.referrer_id == referrer_id,
                Booking.status.in_(["approved_credit", "converted"])
            )
            .scalar()
        )

        # 2. 🔥 FIXED: Query clinical counts from the Bridge, not the Booking header
        grouped = (
            db.query(
                Booking.booking_code,
                func.sum(Booking.total_amount).label("booking_total"),
                # Subquery to count actual patient entries in the batch link table
                db.query(func.count(ReferralBridge.id))
                  .filter(ReferralBridge.batch_uid == Booking.booking_code)
                  .as_scalar()
                  .label("patients_count"),
                func.max(Booking.created_at).label("created_at")
            )
            .filter(
                Booking.referrer_id == referrer_id,
                Booking.status.in_(["approved_credit", "converted"])
            )
            .group_by(Booking.booking_code)
            .order_by(func.max(Booking.created_at).desc())
            .all()
        )

        return {
            "total_credit": float(total_credit),
            "bookings": [
                {
                    "booking_code": g.booking_code,
                    "booking_total": float(g.booking_total),
                    "patients_count": g.patients_count, # Now shows '2'
                    "created_at": g.created_at
                }
                for g in grouped
            ]
        }


    # ==============================================================
    # DRILL DOWN
    # ==============================================================
    @staticmethod
    def get_booking_details(db: Session, booking_code: str, referrer_id: int):
        # 🔥 FIXED: Pull the actual patient snapshots from the Bridge table
        # This ensures Bello and Safiya both appear in the list.
        rows = (
            db.query(ReferralBridge)
            .filter(ReferralBridge.batch_uid == booking_code)
            .all()
        )

        return [
            {
                "full_name": r.patient_name,
                "phone": "-", # Bridged patients use snapshots
                "amount": 0,   # Financial details stay in the Booking header
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
        
        p_service = PatientService(db, current_user)
        booking_service = BookingService(db)

        try:
            # 1. THE COLLECTOR PHASE (PRE-BOOKING)
            # We don't save the batch yet; we collect the data first.
            master_booking_items = []
            patient_conversion_map = [] 

            for row in batch_data["patients"]:
                patient_info = row.get("patient_info")
                test_ids = row.get("test_ids", [])
                if not patient_info: continue

                new_patient = p_service.create(PatientCreate(**patient_info))

                for tid in test_ids:
                    master_booking_items.append({
                        "test_type_id": tid, 
                        "patient_id": new_patient.id,
                        "patient_name": new_patient.full_name, 
                        "patient_phone": new_patient.phone
                    })
                
                patient_conversion_map.append({
                    "patient": new_patient, 
                    "sample_type": row.get("sample_type")
                })

            # ---------------------------------------------------------
            # 2. FINANCIAL AUTHORITY (CORE-2) GENERATES THE UNIFIED ID
            # ---------------------------------------------------------
            # We call the booking service first to get the authoritative SLB- code.
            booking = booking_service.create_booking(
                "referral",
                batch_data.get("referrer_name"),
                batch_data.get("referrer_phone") or current_user.username,
                None,
                master_booking_items,
                billing_mode="credit",
                referrer_id=batch_data["referrer_id"]
            )
            booking.status = "approved_credit"
            db.flush() 

            # 🔥 THE UNIFIED ID: This is the only ID that matters now.
            unified_id = booking.booking_code

            # ---------------------------------------------------------
            # 3. CREATE BATCH HEADER & BRIDGE USING THE UNIFIED ID
            # ---------------------------------------------------------
            batch = ReferralBatch(
                batch_uid=unified_id,  # Use SLB- code here
                referrer_id=batch_data["referrer_id"],
                date_received=batch_data.get("date_received"),
                date_due=batch_data.get("date_due") or batch_data.get("date_received"),
                status="Pending"
            )
            db.add(batch)

            # 4. MULTI-PATIENT SILENT CONVERSION
            for entry in patient_conversion_map:
                p_obj = entry["patient"]
                created_requests = BookingConversionService.convert_patient(
                    db=db,
                    booking_id=booking.id,
                    patient_id=p_obj.id,
                    branch_id=current_user.branch_id or 1,
                    cashier_name=f"{current_user.username} (Batch-Sync)"
                )
                
                for req in created_requests:
                    req.status = "paid"
                    # Link everything to the authoritative unified_id
                    db.add(ReferralBridge(
                        batch_uid=unified_id, # Use SLB- code here
                        test_request_id=req.id,
                        patient_name=p_obj.full_name,
                        sample_type=entry["sample_type"]
                    ))

            # 5. FINAL FINANCIALS & LEDGER
            discount_percent = float(batch_data["financials"].get("discount", 0))
            ledger = ReferralLedger(
                batch_uid=unified_id, # Use SLB- code here
                referrer_id=batch_data["referrer_id"],
                gross_total=float(booking.total_amount),
                discount_percent=discount_percent,
                net_payable=float(booking.total_amount) * (1 - (discount_percent / 100)),
                is_settled=False
            )
            db.add(ledger)

            db.commit()
            db.refresh(batch)
            return batch

        except Exception as e:
            db.rollback()
            raise HTTPException(status_code=500, detail=f"Consolidated Sync Failed: {str(e)}")
        
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
