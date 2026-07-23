# -*- coding: utf-8 -*-
# app/services/subscription_service.py
from __future__ import annotations

from datetime import datetime, timedelta
from typing import Optional

from sqlalchemy.orm import Session

from app.models.subscription import Subscription, SubscriptionTier, TrialRecord
from app.models.system_config import SystemConfig


class SubscriptionService:

    def __init__(self, db: Session):
        self.db = db

    # --------------------------------------------------
    # TIER MANAGEMENT
    # --------------------------------------------------

    def get_tier_by_name(self, name: str) -> Optional[SubscriptionTier]:
        return (
            self.db.query(SubscriptionTier)
            .filter(SubscriptionTier.name == name)
            .first()
        )

    def list_tiers(self) -> list[SubscriptionTier]:
        return (
            self.db.query(SubscriptionTier)
            .filter(SubscriptionTier.is_active == True)
            .all()
        )

    # --------------------------------------------------
    # SUBSCRIPTION MANAGEMENT
    # --------------------------------------------------

    def create_trial(
        self,
        lab_name: str,
        branch_id: Optional[int] = None,
        trial_days: int = 30
    ) -> Subscription:
        """Create a new free trial subscription."""
        tier = self.get_tier_by_name("free_trial")
        if not tier:
            raise ValueError("free_trial tier not seeded. Run seed_tiers() first.")

        now = datetime.utcnow()
        expires = now + timedelta(days=trial_days)

        sub = Subscription(
            lab_name=lab_name,
            branch_id=branch_id,
            tier_id=tier.id,
            status="trial",
            started_at=now,
            expires_at=expires,
            is_trial=True,
        )
        self.db.add(sub)
        self.db.flush()

        trial = TrialRecord(
            subscription_id=sub.id,
            started_at=now,
            expires_at=expires,
            is_converted=False,
        )
        self.db.add(trial)
        self.db.commit()
        self.db.refresh(sub)
        return sub

    def get_active_subscription(self) -> Optional[Subscription]:
        """Returns the current active or trial subscription."""
        return (
            self.db.query(Subscription)
            .filter(Subscription.status.in_(["trial", "active"]))
            .order_by(Subscription.created_at.desc())
            .first()
        )

    def get_subscription_status(self) -> dict:
        """Full status summary for the current subscription."""
        sub = self.get_active_subscription()
        if not sub:
            return {
                "has_subscription": False,
                "status": "none",
                "tier": None,
                "expires_at": None,
                "is_expired": True,
                "ai_tier": 0,
                "features": {}
            }

        now = datetime.utcnow()
        is_expired = sub.expires_at < now

        if is_expired and sub.status in ["trial", "active"]:
            sub.status = "expired"
            self.db.commit()

        return {
            "has_subscription": True,
            "status": sub.status,
            "lab_name": sub.lab_name,
            "tier": sub.tier.name,
            "tier_display": sub.tier.display_name,
            "is_trial": sub.is_trial,
            "started_at": sub.started_at.isoformat(),
            "expires_at": sub.expires_at.isoformat(),
            "is_expired": is_expired,
            "ai_tier": sub.tier.ai_tier,
            "ai_calls_per_day": sub.tier.ai_calls_per_day,
            "features": {
                "blood_bank": sub.tier.blood_bank_enabled,
                "analytics": sub.tier.analytics_enabled,
                "max_users": sub.tier.max_users,
                "max_patients": sub.tier.max_patients,
            }
        }

    def upgrade_subscription(
        self,
        subscription_id: int,
        new_tier_name: str,
        duration_days: int = 30
    ) -> Subscription:
        """Upgrade an existing subscription to a new tier."""
        sub = self.db.query(Subscription).filter(
            Subscription.id == subscription_id
        ).first()
        if not sub:
            raise ValueError(f"Subscription {subscription_id} not found.")

        tier = self.get_tier_by_name(new_tier_name)
        if not tier:
            raise ValueError(f"Tier '{new_tier_name}' not found.")

        now = datetime.utcnow()
        sub.tier_id = tier.id
        sub.status = "active"
        sub.is_trial = False
        sub.started_at = now
        sub.expires_at = now + timedelta(days=duration_days)

        # Mark trial as converted if applicable
        trial = self.db.query(TrialRecord).filter(
            TrialRecord.subscription_id == sub.id,
            TrialRecord.is_converted == False
        ).first()
        if trial:
            trial.is_converted = True
            trial.converted_at = now

        self.db.commit()
        self.db.refresh(sub)
        return sub

    # --------------------------------------------------
    # SYSTEM CONFIG HELPERS
    # --------------------------------------------------

    def get_config(self, key: str) -> Optional[str]:
        row = self.db.query(SystemConfig).filter(
            SystemConfig.key == key
        ).first()
        return row.value if row else None

    def set_config(self, key: str, value: str) -> None:
        row = self.db.query(SystemConfig).filter(
            SystemConfig.key == key
        ).first()
        if row:
            row.value = value
        else:
            row = SystemConfig(key=key, value=value)
            self.db.add(row)
        self.db.commit()

    def is_first_run(self) -> bool:
        val = self.get_config("first_run")
        return val is None or val == "true"

    def mark_first_run_complete(self) -> None:
        self.set_config("first_run", "false")

    # --------------------------------------------------
    # FEATURE GATE CHECKS
    # --------------------------------------------------

    def can_use_ai_tier2(self) -> bool:
        status = self.get_subscription_status()
        return not status["is_expired"] and status.get("ai_tier", 0) >= 2

    def can_use_blood_bank(self) -> bool:
        status = self.get_subscription_status()
        return not status["is_expired"] and status["features"].get("blood_bank", False)

    def can_use_analytics(self) -> bool:
        status = self.get_subscription_status()
        return not status["is_expired"] and status["features"].get("analytics", False)