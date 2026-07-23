# -*- coding: utf-8 -*-
# app/core/subscription_guard.py
from __future__ import annotations

from fastapi import HTTPException, Depends
from sqlalchemy.orm import Session

from app.api.deps import get_db
from app.services.subscription_service import SubscriptionService


def require_active_subscription(db: Session = Depends(get_db)):
    """
    Dependency — blocks endpoint if subscription is expired or missing.
    Use on any route that requires an active subscription.
    """
    svc = SubscriptionService(db)
    status = svc.get_subscription_status()

    if not status["has_subscription"]:
        raise HTTPException(
            status_code=403,
            detail="No subscription found. Please activate a trial or subscription."
        )
    if status["is_expired"]:
        raise HTTPException(
            status_code=403,
            detail=f"Subscription expired. Current tier: {status.get('tier')}. Please renew."
        )


def require_ai_tier2(db: Session = Depends(get_db)):
    """
    Dependency — blocks endpoint if subscription does not include
    Tier 2 AI (Claude API access).
    """
    svc = SubscriptionService(db)
    if not svc.can_use_ai_tier2():
        raise HTTPException(
            status_code=403,
            detail="Claude AI access requires Pro or Enterprise subscription."
        )


def require_blood_bank(db: Session = Depends(get_db)):
    """
    Dependency — blocks blood banking endpoints for tiers that don't include it.
    """
    svc = SubscriptionService(db)
    if not svc.can_use_blood_bank():
        raise HTTPException(
            status_code=403,
            detail="Blood Banking module requires Pro or Enterprise subscription."
        )


def require_analytics(db: Session = Depends(get_db)):
    """
    Dependency — blocks analytics endpoints for basic/trial tiers.
    """
    svc = SubscriptionService(db)
    if not svc.can_use_analytics():
        raise HTTPException(
            status_code=403,
            detail="Analytics module requires Pro or Enterprise subscription."
        )