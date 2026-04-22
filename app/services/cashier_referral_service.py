# -*- coding: utf-8 -*-
from sqlalchemy.orm import Session
from fastapi import HTTPException
from sqlalchemy import func
from datetime import datetime

# Models
from app.models.cashier_referral import ReferralStore, ReferralData, ReferralFinancialRecord
from app.models.test_type import TestType
from app.models.test_request import TestRequest
from app.models.payment import Payment

# Schemas
from app.schemas.cashier_referral import CashierReferralSyncRequest
from app.schemas.patient import PatientCreate

# Existing Services
from app.services.patient_service import PatientService

class CashierReferralService:
    @staticmethod
    def sync_and_convert(db: Session, data: CashierReferralSyncRequest, current_user):
        """
        Atomic Orchestration:
        1. ReferralStore: Archive the Referrer's intent (immutable).
        2. PatientService: Generate authoritative Lab IDs (IEL-YY-NNNN).
        3. TestRequest: Create the clinical worklist.
        4. ReferralFinancialRecord: Apply discounts & track balance.
        5. Payment: Seal the transaction in the main Lab ledger.
        """
        p_service = PatientService(db, current_user)
        
        try:
            # --- PHASE 1: GENERATE UNIFIED BATCH CODE ---
            # Format: REF-BRANCH-YYMMDD-TIME
            timestamp = datetime.now().strftime("%y%m%d-%H%M%S")
            batch_code = f"REF-{current_user.branch_id}-{timestamp}"
            
            total_gross = 0.0
            all_request_ids = []

            # --- PHASE 2: PROCESSING PATIENTS ---
            for p_entry in data.patients:
                # 1. Record the Intent (Archive)
                store_entry = ReferralStore(
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
                db.add(store_entry)
                db.flush()

                # 2. Create Clinical Identity (PatientService)
                # This triggers the IEL-YY-NNNN auto-generation logic
                patient_obj = p_service.create(PatientCreate(
                    full_name=p_entry.full_name,
                    phone=p_entry.phone,
                    gender=p_entry.gender,
                    date_of_birth=p_entry.dob,
                    branch_id=current_user.branch_id
                ))

                # 3. Resolve Clinical Requests & Prices
                # We pull prices from TestType to ensure financial accuracy
                last_req_id = None
                for t_id in p_entry.test_type_ids:
                    test_type = db.query(TestType).filter(TestType.id == t_id).first()
                    if not test_type:
                        raise HTTPException(status_code=404, detail=f"Test Type {t_id} not found")
                    
                    total_gross += float(test_type.price)

                    new_request = TestRequest(
                        patient_id=patient_obj.id,
                        test_type_id=t_id,
                        status="paid", # Authorized by the referral credit
                        requested_by=data.clinician_name,
                        branch_id=current_user.branch_id
                    )
                    db.add(new_request)
                    db.flush()
                    all_request_ids.append(new_request.id)
                    last_req_id = new_request.id

                # 4. Create the Bridge
                db.add(ReferralData(
                    store_id=store_entry.id,
                    patient_id=patient_obj.id,
                    test_request_id=last_req_id,
                    status="converted"
                ))

            # --- PHASE 3: FINANCIAL AUTHORITY ---
            discount_pct = float(data.financials.discount_percent)
            net_amount = total_gross * (1 - (discount_pct / 100))

            # A. Create the Main Ledger Entry (For Lab accounting)
            # We bypass the PaymentService.create validation to allow patient_id=None
            main_payment = Payment(
                patient_id=None, # Batch payment identification
                amount=net_amount,
                method=data.financials.payment_method,
                status="completed",
                notes=f"BATCH:{batch_code}",
                branch_id=current_user.branch_id,
                created_by_id=current_user.id,
                request_ids_csv=",".join(map(str, all_request_ids))
            )
            db.add(main_payment)
            db.flush()

            # B. Create the Referral Ledger (For CST Hospital's balance)
            db.add(ReferralFinancialRecord(
                batch_code=batch_code,
                referrer_id=data.referrer_id,
                gross_total=total_gross,
                discount_percent=discount_pct,
                net_payable=net_amount,
                payment_id=main_payment.id,
                is_settled=False
            ))

            db.commit()
            return {
                "status": "Success", 
                "batch_code": batch_code, 
                "total_patients": len(data.patients),
                "net_payable": net_amount
            }

        except Exception as e:
            db.rollback()
            # Log exact error for debugging in the cloud
            print(f"DEBUG: Referral Sync Failed: {str(e)}")
            raise HTTPException(status_code=500, detail=f"Sovereign Sync Failure: {str(e)}")
