# -*- coding: utf-8 -*-
from __future__ import annotations

from sqlalchemy.orm import Session
from app.db.session import engine, SessionLocal
from app.db.base import Base
from app.core.security import hash_password

# --- EXISTING MODELS ---
from app.models.patient import Patient  # noqa
from app.models.test_type import TestType  # noqa
from app.models.test_template import TestTemplate  # noqa
from app.models.test_request import TestRequest  # noqa
from app.models.test_result import TestResult  # noqa
from app.models.audit_log import AuditLog  # noqa
from app.models.branch import Branch  # noqa
from app.models.user import User  # noqa
from app.models.booking import Booking  # noqa
from app.models.booking_item import BookingItem  # noqa
from app.models.referrer import Referrer # noqa

# --- 🔥 NEW CASHIER AUTHORITY TRIAD ---
# Import the new clean-room tables here
from app.models.cashier_referral import (
    ReferralStore,
    ReferralData,
    ReferralFinancialRecord
) # noqa

def bootstrap(db: Session):
    # Branch Logic
    if db.query(Branch).count() == 0:
        hq = Branch(
            name="Head Office",
            code="SLB-001",
            address="Main Branch"
        )
        db.add(hq)
        db.commit()
        db.refresh(hq)

    # Super Admin Logic
    if db.query(User).count() == 0:
        admin = User(
            username="Profnur",
            password_hash=hash_password("@Zulnur4eva"),
            role="super_admin",
            branch_id=None,
        )
        db.add(admin)
        db.commit()

def init_db() -> None:
    # This now creates: referral_store, referral_data, and referral_financial_records
    Base.metadata.create_all(bind=engine)

    db: Session = SessionLocal()
    try:
        bootstrap(db)
    finally:
        db.close()
