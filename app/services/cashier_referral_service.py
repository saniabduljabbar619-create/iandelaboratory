# -*- coding: utf-8 -*-
from sqlalchemy.orm import Session
from fastapi import HTTPException
from app.models.cashier_referral import ReferralStore, ReferralData, ReferralFinancialRecord
from app.schemas.cashier_referral import CashierReferralSyncRequest
from app.services.booking_service import BookingService # To generate the SLB code

class CashierReferralService:
    @staticmethod
    def sync_new_batch(db: Session, data: CashierReferralSyncRequest, current_user):
        booking_service = BookingService(db)
        
        try:
            # 1. Generate the Unified Authority Code (SLB-BKG)
            # We use the booking service just to get a unique, sequential code
            batch_code = f"REF-{current_user.branch_id}-{func.now().strftime('%y%m%d%H%M%S')}" 
            # Note: You can also use booking_service.generate_code() if available
            
            total_gross = 0.0

            for p_entry in data.patients:
                # 2. Populate REFERRAL STORE (The Immutable Archive)
                new_store_entry = ReferralStore(
                    batch_code=batch_code,
                    facility_name=data.facility_name,
                    facility_phone=data.facility_phone,
                    facility_address=data.facility_address,
                    clinician_name=data.clinician_name,
                    patient_name_snapshot=p_entry.full_name,
                    patient_phone_snapshot=p_entry.phone,
                    test_types_csv=",".join(map(str, p_entry.test_type_ids)),
                    sample_type=p_entry.sample_type,
                    branch_id=current_user.branch_id
                )
                db.add(new_store_entry)
                db.flush() # Get the ID for the next table

                # 3. Populate REFERRAL DATA (The Clinical Bridge)
                db.add(ReferralData(
                    store_id=new_store_entry.id,
                    bio_gender=p_entry.gender,
                    bio_dob=p_entry.dob,
                    status="pending"
                ))

            # 4. Calculate Economics & Populate FINANCIAL RECORD
            # (In a real scenario, you'd fetch prices from test_types here)
            # For brevity, let's assume total_gross is calculated from the UI payload or DB
            net_payable = total_gross * (1 - (data.financials.discount_percent / 100))

            db.add(ReferralFinancialRecord(
                batch_code=batch_code,
                referrer_id=data.referrer_id,
                gross_total=total_gross,
                discount_percent=data.financials.discount_percent,
                net_payable=net_payable,
                is_settled=False
            ))

            db.commit()
            return {"batch_code": batch_code, "status": "Success"}

        except Exception as e:
            db.rollback()
            raise HTTPException(status_code=500, detail=f"Sovereign Sync Failed: {str(e)}")
