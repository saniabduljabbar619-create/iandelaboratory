# -*- coding: utf-8 -*-
# app/models/subscription.py
from __future__ import annotations
import uuid
from sqlalchemy import (
    Column, Integer, String, DateTime, Numeric,
    Boolean, Enum, ForeignKey, func
)
from sqlalchemy.orm import relationship
from app.db.base import Base


class SubscriptionTier(Base):
    """Defines what each plan level unlocks."""
    __tablename__ = "subscription_tiers"

    id = Column(Integer, primary_key=True)
    name = Column(String(50), unique=True, nullable=False)
    # free_trial | basic | pro | enterprise
    display_name = Column(String(100), nullable=False)
    ai_tier = Column(Integer, default=1, nullable=False)
    # 1 = Tier1 rule-based only | 2 = Claude API enabled
    ai_calls_per_day = Column(Integer, nullable=True)
    # NULL = unlimited
    max_users = Column(Integer, nullable=True)
    max_patients = Column(Integer, nullable=True)
    blood_bank_enabled = Column(Boolean, default=False)
    analytics_enabled = Column(Boolean, default=False)
    price_monthly = Column(Numeric(12, 2), nullable=True)
    is_active = Column(Boolean, default=True)
    created_at = Column(DateTime, server_default=func.now())


class Subscription(Base):
    """One subscription record per lab installation."""
    __tablename__ = "subscriptions"

    id = Column(Integer, primary_key=True)
    sync_id = Column(
        String(36), unique=True, index=True,
        default=lambda: str(uuid.uuid4())
    )
    lab_name = Column(String(255), nullable=False)
    branch_id = Column(Integer, ForeignKey("branches.id"), nullable=True)
    tier_id = Column(Integer, ForeignKey("subscription_tiers.id"), nullable=False)

    status = Column(
        Enum("trial", "active", "expired", "suspended",
             name="subscription_status"),
        nullable=False,
        default="trial"
    )

    started_at = Column(DateTime, nullable=False)
    expires_at = Column(DateTime, nullable=False)
    is_trial = Column(Boolean, default=True, nullable=False)

    created_at = Column(DateTime, server_default=func.now())
    updated_at = Column(DateTime, server_default=func.now(), onupdate=func.now())

    tier = relationship("SubscriptionTier")
    branch = relationship("Branch")


class TrialRecord(Base):
    """Tracks trial lifecycle — start, expiry, conversion."""
    __tablename__ = "trial_records"

    id = Column(Integer, primary_key=True)
    subscription_id = Column(
        Integer, ForeignKey("subscriptions.id"), nullable=False
    )
    started_at = Column(DateTime, nullable=False)
    expires_at = Column(DateTime, nullable=False)
    converted_at = Column(DateTime, nullable=True)
    is_converted = Column(Boolean, default=False, nullable=False)
    created_at = Column(DateTime, server_default=func.now())

    subscription = relationship("Subscription")