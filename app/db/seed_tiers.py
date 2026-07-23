# -*- coding: utf-8 -*-
# app/db/seed_tiers.py
"""
Run once to seed the subscription tiers into the database.
Usage: python -m app.db.seed_tiers
"""
from __future__ import annotations

from app.db.session import SessionLocal
from app.models.subscription import SubscriptionTier


TIERS = [
    {
        "name": "free_trial",
        "display_name": "Free Trial",
        "ai_tier": 1,
        "ai_calls_per_day": 10,
        "max_users": 3,
        "max_patients": 100,
        "blood_bank_enabled": False,
        "analytics_enabled": False,
        "price_monthly": None,
    },
    {
        "name": "basic",
        "display_name": "Basic Plan",
        "ai_tier": 1,
        "ai_calls_per_day": 50,
        "max_users": 5,
        "max_patients": 500,
        "blood_bank_enabled": False,
        "analytics_enabled": False,
        "price_monthly": 15000.00,
    },
    {
        "name": "pro",
        "display_name": "Pro Plan",
        "ai_tier": 2,
        "ai_calls_per_day": None,
        "max_users": 20,
        "max_patients": None,
        "blood_bank_enabled": True,
        "analytics_enabled": True,
        "price_monthly": 35000.00,
    },
    {
        "name": "enterprise",
        "display_name": "Enterprise Plan",
        "ai_tier": 2,
        "ai_calls_per_day": None,
        "max_users": None,
        "max_patients": None,
        "blood_bank_enabled": True,
        "analytics_enabled": True,
        "price_monthly": 75000.00,
    },
]


def seed():
    db = SessionLocal()
    try:
        existing = db.query(SubscriptionTier).count()
        if existing > 0:
            print(f"Tiers already seeded ({existing} found). Skipping.")
            return

        for t in TIERS:
            db.add(SubscriptionTier(**t))
        db.commit()
        print(f"✅ Seeded {len(TIERS)} subscription tiers successfully.")
    finally:
        db.close()


if __name__ == "__main__":
    seed()