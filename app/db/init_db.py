# -*- coding: utf-8 -*-
from __future__ import annotations

from sqlalchemy.orm import Session

from app.db.session import engine, SessionLocal
from app.db.base import Base

from app.core.security import hash_password

# Import models so Base.metadata is populated
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


def bootstrap(db: Session):
    if db.query(Branch).count() == 0:
        hq = Branch(
            name="Head Office",
            code="SLB-001",
            address="Main Branch"
        )
        db.add(hq)
        db.commit()
        db.refresh(hq)

    if db.query(User).count() == 0:
        admin = User(
            username="Profnur",
            password_hash=hash_password("@Zulnur4ever"),
            role="super_admin",
            branch_id=None,
        )
        db.add(admin)
        db.commit()


def init_db() -> None:
    Base.metadata.create_all(bind=engine)

    db: Session = SessionLocal()
    try:
        bootstrap(db)
    finally:
        db.close()
