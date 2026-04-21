# -*- coding: utf-8 -*-
# app/services/referrer_service.py

from sqlalchemy import func
from sqlalchemy.orm import Session
from fastapi import HTTPException
from sqlalchemy.exc import SQLAlchemyError

# --- MODELS (The Authority Layer) [cite: 191] ---
from app.models.booking import Booking
from app.models.referrer import Referrer
from app.models.referral_batch import ReferralBatch
from app.models.referral_bridge import ReferralBridge # Authority for Batch Linkage
from app.models.referral_ledger import ReferralLedger
from app.models.test_request import TestRequest        # Clinical Reality [cite: 49]
from app.models.test_type import TestType              # Financial Authority [cite: 19]
from app.models.patient import Patient                  # Identity Authority [cite: 19]

# --- SCHEMAS ---
from app.schemas.patient import PatientCreate

class ReferrerService:

    # ==============================================================
    # DASHBOARD: Unified Authority View [cite: 111]
    # ==============================================================
    @staticmethod
    def get_dashboard(db: Session, referrer_id: int):
        """Retrieves deterministic financial totals and clinical counts."""
        # 1. Financial Authority (Core-2 Commerce Layer) [cite: 62, 132]
        total_credit = (
            db.query(func.coalesce(func.sum(Booking.total_amount), 0))
            .filter(
                Booking.referrer_id == referrer_id,
                Booking.status.in_(["approved_credit", "converted"])
            ).scalar()
        )

        # 2. Grouped Reality View (Core-1 Enforcement Layer) [cite: 55, 116]
        grouped = (
            db.query(
                Booking.booking_code,
                func.sum(Booking.total_amount).label("booking_total"),
                # Subquery counts actual clinical links sharing the unified fingerprint
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
                    "patients_count": g.patients_count, 
                    "created_at": g.created_at
                } for g in grouped
            ]
        }

    # ==============================================================
    # DRILL DOWN: The Quad-Join (Identity, Reality, and Money)
    # ==============================================================
    @staticmethod
    def get_booking_details(db: Session, booking_code: str, referrer_id: int):
        from app.models.test_request import TestRequest
        from app.models.test_type import TestType
        from app.models.patient import Patient 

        try:
            # 🔥 THE MASTER AUTHORITY JOIN
            # We explicitly select FROM the Bridge to resolve SQL ambiguity
            results = (
                db.query(
                    Patient.full_name,
                    Patient.phone,
                    TestType.price.label("test_price"), 
                    TestRequest.created_at.label("clinical_date")
                )
                .select_from(ReferralBridge) # Explicit root of the join chain
                .join(TestRequest, ReferralBridge.test_request_id == TestRequest.id)
                .join(Patient, TestRequest.patient_id == Patient.id)
                .join(TestType, TestRequest.test_type_id == TestType.id)
                .filter(ReferralBridge.batch_uid == booking_code)
                .all()
            )

            return [
                {
                    "full_name": r.full_name,
                    "phone": r.phone or "0000000000", 
                    "amount": float(r.test_price) if r.test_price else 0.0,
                    # Audit-compliant date formatting
                    "created_at": r.clinical_date.strftime("%Y-%m-%d %H:%M") if r.clinical_date else "N/A"
                }
                for r in results
            ]
        except Exception as e:
            # Audit the failure for technical oversight
            print(f"[CORE-1 AUDIT FAILURE] Dashboard resolution error: {str(e)}")
            raise HTTPException(status_code=500, detail="Authority failed to resolve clinical details.")

    # ==============================================================    
    # SMART BATCH SYNC: Single Point of Authority [cite: 111]
    # ==============================================================
    @staticmethod
    def create_referral_batch_sync(db: Session, batch_data: dict, current_user):
        """Atomically synchronizes UI input with the centralized enforcement brain."""
        from app.services.booking_service import BookingService
        from app.services.booking_conversion_service import BookingConversionService
        from app.services.patient_service import PatientService
        
        p_service = PatientService(db, current_user)
        booking_service = BookingService(db)

        try:
            # 1. Collector Phase
            master_booking_items = []
            patient_conversion_map = [] 

            for row in batch_data["patients"]:
                p_info = row.get("patient_info")
                if not p_info: continue

                # Resolve authoritative patient record
                new_patient = p_service.create(PatientCreate(**p_info))

                for tid in row.get("test_ids", []):
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

            # 2. Centralized Authority: Generate SLB code [cite: 191]
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

            # 🔥 THE UNIFIED ID: The fingerprint binding all layers [cite: 111]
            unified_id = booking.booking_code

            # 3. Bridge & Conversion (Enforcement Reality) [cite: 117]
            for entry in patient_conversion_map:
                p_obj = entry["patient"]
                requests = BookingConversionService.convert_patient(
                    db=db,
                    booking_id=booking.id,
                    patient_id=p_obj.id,
                    branch_id=current_user.branch_id or 1,
                    cashier_name=f"{current_user.username} (Batch-Sync)"
                )
                
                for req in requests:
                    req.status = "paid"
                    db.add(ReferralBridge(
                        batch_uid=unified_id,
                        test_request_id=req.id,
                        patient_name=p_obj.full_name,
                        sample_type=entry["sample_type"]
                    ))

            # 4. Economic Ledger Compliance [cite: 281]
            db.add(ReferralLedger(
                batch_uid=unified_id,
                referrer_id=batch_data["referrer_id"],
                gross_total=float(booking.total_amount),
                is_settled=False
            ))

            db.commit()
            return booking

        except Exception as e:
            db.rollback() # Ensures fail-closed security [cite: 189]
            raise HTTPException(status_code=500, detail=f"Consolidated Sync Failed: {str(e)}")

    @staticmethod
    def create_referrer(db: Session, name: str, phone: str, email: str = None, credit_limit: float = 0):
        """Registers a doctor or hospital as an external authority tenant."""
        existing = db.query(Referrer).filter(Referrer.phone == phone).first()
        if existing:
            raise HTTPException(status_code=400, detail="Referrer already exists")
        try:
            new_ref = Referrer(name=name, phone=phone, email=email, credit_limit=credit_limit, is_active=True)
            db.add(new_ref)
            db.commit()
            db.refresh(new_ref)
            return new_ref
        except SQLAlchemyError as e:
            db.rollback()
            raise HTTPException(status_code=500, detail=str(e))
