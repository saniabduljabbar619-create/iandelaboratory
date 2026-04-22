# -*- coding: utf-8 -*-
from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session
from app.db.session import get_db
from app.schemas.cashier_referral import CashierReferralSyncRequest
from app.services.cashier_referral_service import CashierReferralService
from app.api.deps import get_current_user

router = APIRouter()

@router.post("/sync")
def sync_referral_batch(
    data: CashierReferralSyncRequest,
    db: Session = Depends(get_db),
    current_user = Depends(get_current_user)
):
    """Entry point for the Cashier Referral Wizard."""
    return CashierReferralService.sync_new_batch(db, data, current_user)

@router.get("/dashboard-stats")
def get_cashier_stats(referrer_id: int, db: Session = Depends(get_db)):
    """Simple, fast query from the new sovereign tables."""
    # Logic to query referral_financial_records and referral_store directly
    pass
