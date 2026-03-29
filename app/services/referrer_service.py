# app/services/referrer_service.py
from sqlalchemy import func
from app.models.booking import Booking
from app.models.referral_batch import ReferralBatch
from app.models.referral_bridge import ReferralBridge
from app.models.referral_ledger import ReferralLedger
from app.services.patient_service import patient_service
from app.services.test_request_service import test_request_service

class ReferrerService:

    @staticmethod
    def get_dashboard(db, referrer_id: int):
        # ... (Your existing get_dashboard code remains same) ...
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
    def get_booking_details(db, booking_code: str, referrer_id: int):
        # ... (Your existing get_booking_details code remains same) ...
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
    async def create_referral_batch_sync(db, batch_data: dict):
        """
        Atomically creates a batch by bridging stable clinical logic 
        with the new parallel referral tracking tables.
        """
        # 1. Create the Logistical Envelope
        batch = ReferralBatch(
            batch_uid=batch_data['batch_uid'],
            referrer_id=batch_data['referrer_id'],
            date_received=batch_data['date_received'],
            date_due=batch_data['date_due'],
            courier_info=batch_data.get('courier_info'),
            status="Pending"
        )
        db.add(batch)
        
        # 2. Process patients through STABLE pipelines
        for row in batch_data['patients']:
            # Call your LIVE patient registration logic
            new_patient = await patient_service.create_patient(db, row['patient_info'])
            
            # Call your LIVE test request logic
            # This ensures results, snapshots, and logs are generated normally
            for test_type_id in row['test_ids']:
                live_request = await test_request_service.create_request(
                    db, 
                    patient_id=new_patient.id, 
                    test_type_id=test_type_id
                )

                # 3. Create the Smart Bridge Link
                bridge = ReferralBridge(
                    batch_uid=batch.batch_uid,
                    test_request_id=live_request.id,
                    patient_name=new_patient.full_name,
                    sample_type=row['sample_type']
                )
                db.add(bridge)

        # 4. Create Parallel Ledger Record
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
        
        # Atomic Commit: If any step fails, nothing is saved.
        db.commit()
        db.refresh(batch)
        return batch