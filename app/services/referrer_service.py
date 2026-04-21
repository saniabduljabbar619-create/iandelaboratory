# -*- coding: utf-8 -*-
# app/services/referrer_service.py

from sqlalchemy import func
from sqlalchemy.orm import Session
from fastapi import HTTPException
from sqlalchemy.exc import SQLAlchemyError

# --- MODELS (The Authority Layer) ---
from app.models.booking import Booking
from app.models.referrer import Referrer
from app.models.referral_batch import ReferralBatch
from app.models.referral_bridge import ReferralBridge # Authority for the Batch Link
from app.models.referral_ledger import ReferralLedger
from app.models.test_request import TestRequest        # Clinical Reality
from app.models.test_type import TestType              # Financial Authority
from app.models.patient import Patient                  # Identity Authority

# --- SCHEMAS ---
from app.schemas.patient import PatientCreate

class ReferrerService:

    # ==============================================================
    # DASHBOARD: Unified Authority View
    # ==============================================================
    @staticmethod
    def get_dashboard(db: Session, referrer_id: int):
        """Retrieves deterministic financial totals and patient counts."""
        # 1. Total Credit: Commerce Authority (Core-2)
        total_credit = (
            db.query(func.coalesce(func.sum(Booking.total_amount), 0))
            .filter(
                Booking.referrer_id == referrer_id,
                Booking.status.in_(["approved_credit", "converted"])
            ).scalar()
        )

        # 2. Grouped View: Links Financial Header with Clinical Reality
        grouped = (
            db.query(
                Booking.booking_code,
                func.sum(Booking.total_amount).label("booking_total"),
                # Subquery to count actual clinical records linked to this SLB- code
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
    # DRILL DOWN: The Quad-Join (The Deterministic Truth)
    # ==============================================================
    @staticmethod
    def get_booking_details(db: Session, booking_code: str, referrer_id: int):
        """Bridges Identity, Clinical Audit, and Financial Authority into one view."""
        try:
            # 🔥 THE MASTER JOIN: Pulls Live Identity from the Patient table
            # Resolves ambiguity by defining 'ReferralBridge' as the explicit root.
            results = (
                db.query(
                    Patient.full_name,
                    Patient.phone,
                    TestType.price.label("test_price"), 
                    TestRequest.created_at.label("clinical_date")
                )
                .select_from(ReferralBridge) 
                .join(TestRequest, ReferralBridge.test_request_id == TestRequest.id)
                .join(Patient, TestRequest.patient_id == Patient.id)
                .join(TestType, TestRequest.test_type_id == TestType.id)
                .filter(ReferralBridge.batch_uid == booking_code)
                .all()
            )

            return [
                {
                    "full_name": r.full_name, # Authoritative Full Name
                    "phone": r.phone or "0000000000", 
                    "amount": float(r.test_price) if r.test_price else 0.0,
                    "created_at": r.clinical_date.strftime("%Y-%m-%d %H:%M") if r.clinical_date else "N/A"
                }
                for r in results
            ]
        except Exception as e:
            print(f"[CORE-1 AUDIT FAILURE] Drill-down resolution error: {str(e)}")
            raise HTTPException(status_code=500, detail="Authority failed to resolve clinical details.")

    # ==============================================================    
    # SMART BATCH SYNC: Single Point of Authority
    # ==============================================================
    @staticmethod
    def create_referral_batch_sync(db: Session, batch_data: dict, current_user):
        """Atomically synchronizes UI input with the centralized enforcement brain."""
        from app.services.patient_service import PatientService
        from app.services.booking_service import BookingService
        from app.services.booking_conversion_service import BookingConversionService
        
        p_service = PatientService(db, current_user)
        booking_service = BookingService(db)

        try:
            # 1. Collector Phase
            master_booking_items = []
            patient_conversion_map = [] 

            for row in batch_data["patients"]:
                p_info = row.get("patient_info")
                if not p_info: continue
                new_patient = p_service.create(PatientCreate(**p_info))
                for tid in row.get("test_ids", []):
                    master_booking_items.append({
                        "test_type_id": tid, 
                        "patient_id": new_patient.id,
                        "patient_name": new_patient.full_name, 
                        "patient_phone": new_patient.phone
                    })
                patient_conversion_map.append({"patient": new_patient, "sample_type": row.get("sample_type")})

            # 2. Central Authority: Generate SLB code
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

            # 🔥 FIXED: Use 'booking_code' (verified from terminal)
            unified_id = booking.booking_code

            # 3. Batch Header
            db.add(ReferralBatch(
                batch_uid=unified_id,
                referrer_id=batch_data["referrer_id"],
                date_received=batch_data.get("date_received"),
                date_due=batch_data.get("date_due") or batch_data.get("date_received"),
                status="Pending"
            ))

            # 4. Conversion & Bridge Reality
            for entry in patient_conversion_map:
                p_obj = entry["patient"]
                requests = BookingConversionService.convert_patient(
                    db=db, booking_id=booking.id, patient_id=p_obj.id,
                    branch_id=current_user.branch_id or 1,
                    cashier_name=f"{current_user.username} (Batch-Sync)"
                )
                for req in requests:
                    req.status = "paid"
                    db.add(ReferralBridge(
                        batch_uid=unified_id, test_request_id=req.id,
                        patient_name=p_obj.full_name, sample_type=entry["sample_type"]
                    ))

            # 5. 🔥 FINANCIALS: Calculate 'net_payable' to satisfy schema 
            financials = batch_data.get("financials", {})
            discount_pct = float(financials.get("discount", 0))
            gross = float(booking.total_amount)
            net = gross * (1 - (discount_pct / 100))

            db.add(ReferralLedger(
                batch_uid=unified_id,
                referrer_id=batch_data["referrer_id"],
                gross_total=gross,
                discount_percent=discount_pct,
                net_payable=net, # Prevents the 1048 Error
                is_settled=False,
                payment_method=financials.get("method", "Credit")
            ))

            db.commit()
            return booking

        except Exception as e:
            db.rollback() 
            raise HTTPException(status_code=500, detail=f"Consolidated Sync Failed: {str(e)}")

    @staticmethod
    def create_referrer(db: Session, name: str, phone: str, email: str = None, credit_limit: float = 0):
        existing = db.query(Referrer).filter(Referrer.phone == phone).first()
        if existing:
            raise HTTPException(status_code=400, detail="Referrer exists")
        new_ref = Referrer(name=name, phone=phone, email=email, credit_limit=credit_limit, is_active=True)
        db.add(new_ref)
        db.commit()
        return new_ref
