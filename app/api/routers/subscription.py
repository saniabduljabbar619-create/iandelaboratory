# -*- coding: utf-8 -*-
# app/api/routers/subscription.py
from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from pydantic import BaseModel
from typing import Optional

from app.api.deps import get_db
from app.services.subscription_service import SubscriptionService

router = APIRouter(prefix="/api/subscription", tags=["subscription"])


# --------------------------------------------------
# SCHEMAS
# --------------------------------------------------

class TrialCreateRequest(BaseModel):
    lab_name: str
    branch_id: Optional[int] = None
    trial_days: int = 30


class UpgradeRequest(BaseModel):
    subscription_id: int
    new_tier_name: str
    duration_days: int = 30


# --------------------------------------------------
# ENDPOINTS
# --------------------------------------------------

@router.get("/status")
def get_status(db: Session = Depends(get_db)):
    """Returns the full subscription status of this installation."""
    svc = SubscriptionService(db)
    return svc.get_subscription_status()


@router.get("/tiers")
def list_tiers(db: Session = Depends(get_db)):
    """Lists all available subscription tiers."""
    svc = SubscriptionService(db)
    tiers = svc.list_tiers()
    return [
        {
            "id": t.id,
            "name": t.name,
            "display_name": t.display_name,
            "ai_tier": t.ai_tier,
            "ai_calls_per_day": t.ai_calls_per_day,
            "blood_bank_enabled": t.blood_bank_enabled,
            "analytics_enabled": t.analytics_enabled,
            "price_monthly": float(t.price_monthly) if t.price_monthly else None,
        }
        for t in tiers
    ]


@router.post("/trial")
def activate_trial(payload: TrialCreateRequest, db: Session = Depends(get_db)):
    """Activates a free trial for a new lab installation."""
    svc = SubscriptionService(db)
    existing = svc.get_active_subscription()
    if existing:
        raise HTTPException(
            status_code=400,
            detail=f"An active subscription already exists: {existing.status}"
        )
    sub = svc.create_trial(
        lab_name=payload.lab_name,
        branch_id=payload.branch_id,
        trial_days=payload.trial_days,
    )
    return {
        "message": "Trial activated successfully.",
        "subscription_id": sub.id,
        "lab_name": sub.lab_name,
        "status": sub.status,
        "expires_at": sub.expires_at.isoformat(),
    }


@router.post("/upgrade")
def upgrade(payload: UpgradeRequest, db: Session = Depends(get_db)):
    """Upgrades a subscription to a new tier."""
    svc = SubscriptionService(db)
    try:
        sub = svc.upgrade_subscription(
            subscription_id=payload.subscription_id,
            new_tier_name=payload.new_tier_name,
            duration_days=payload.duration_days,
        )
        return {
            "message": "Subscription upgraded successfully.",
            "subscription_id": sub.id,
            "new_tier": sub.tier.name,
            "status": sub.status,
            "expires_at": sub.expires_at.isoformat(),
        }
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.get("/system/first-run")
def check_first_run(db: Session = Depends(get_db)):
    """Checks if this is the first launch (drives SAS onboarding)."""
    svc = SubscriptionService(db)
    return {"first_run": svc.is_first_run()}


@router.post("/system/first-run/complete")
def complete_first_run(db: Session = Depends(get_db)):
    """Marks first run as complete after SAS onboarding finishes."""
    svc = SubscriptionService(db)
    svc.mark_first_run_complete()
    return {"message": "First run marked complete. SAS onboarding will not repeat."}