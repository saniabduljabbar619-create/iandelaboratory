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

# Import Classes to avoid Circular Dependency and ImportErrors
from app.services.patient_service import PatientService 
from app.services.test_request_service import TestRequestService

class ReferrerService:

    @staticmethod
    def get_dashboard(db: Session, referrer_id: int):
        """ Fetches financial totals and grouped bookings for a referrer. """
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

    @staticmethod
    def get_booking_details(db: Session, booking_code: str, referrer_id: int):
        """ DRILL DOWN: Fetches patient list for a specific booking code. """
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
    # THE SMART SYNC INTEGRATION (FULL THROTTLE)
    # ==============================================================
    @staticmethod
    async def create_referral_batch_sync(db: Session, batch_data: dict, current_user):
        """
        Atomically creates a batch and passes current_user.id 
        to maintain clinical audit logs.
        """
        p_service = PatientService(db, current_user)
        tr_service = TestRequestService(db, current_user)

        # 1. Create Logistical Header
        batch = ReferralBatch(
            batch_uid=batch_data['batch_uid'],
            referrer_id=batch_data['referrer_id'],
            date_received=batch_data['date_received'],
            date_due=batch_data['date_due'],
            status="Pending"
        )
        db.add(batch)
        
        # 2. Process patients and tests
        for row in batch_data['patients']:
            # Create the clinical patient record
            new_patient = p_service.create(row['patient_info'])
            
            for test_type_id in row['test_ids']:
                # CRITICAL FIX: Pass current_user.id as created_by_id
                live_request = await tr_service.create_request(
                    patient_id=new_patient.id, 
                    test_type_id=test_type_id,
                    created_by_id=current_user.id  # Tracking the cashier who committed the batch
                )

                # 3. Create the Smart Bridge Link
                bridge = ReferralBridge(
                    batch_uid=batch.batch_uid,
                    test_request_id=live_request.id,
                    patient_name=new_patient.full_name,
                    sample_type=row['sample_type']
                )
                db.add(bridge)

        # 4. Finalize Ledger and Commit
        ledger = ReferralLedger(
            batch_uid=batch.batch_uid,
            referrer_id=batch.referrer_id,
            gross_total=batch_data['financials']['gross'],
            discount_percent=batch_data['financials']['discount'],
            net_payable=batch_data['financials']['net'],
            is_settled=batch_data['financials']['is_paid'],
            payment_method=batch_data['financials'].get('method')
        )
        db.add(ledger)
        
        db.commit()
        db.refresh(batch)
        return batch

    @staticmethod
    def create_referrer(db: Session, name: str, phone: str, email: str = None, credit_limit: float = 0):
        """ Creates a new Referrer profile (Hospital, Doctor, etc). """
        existing = db.query(Referrer).filter(Referrer.phone == phone).first()
        if existing:
            raise HTTPException(status_code=400, detail="Referrer with this phone already exists")

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