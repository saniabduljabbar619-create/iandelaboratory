from __future__ import annotations

from sqlalchemy import (
    Column,
    Integer,
    String,
    Date,
    DateTime,
    Numeric,
    ForeignKey,
    func
)
from sqlalchemy.orm import relationship
from app.db.base import Base


class Booking(Base):
    __tablename__ = "bookings"

    id = Column(Integer, primary_key=True)

    booking_code = Column(String(50), nullable=False, unique=True, index=True)

    # TEMP COMPATIBILITY FIELDS
    full_name = Column(String(255), nullable=False)
    phone = Column(String(20), nullable=False, index=True)
    email = Column(String(255), nullable=True, index=True)

    dob = Column(Date, nullable=True)
    gender = Column(String(20), nullable=True)

    booking_type = Column(String(20), default="single")

    referrer_name = Column(String(255), nullable=True)
    referrer_phone = Column(String(20), nullable=True)

    total_amount = Column(Numeric(12, 2), nullable=False)
    subtotal_amount = Column(Numeric(12, 2), nullable=True)

    discount_amount = Column(Numeric(12, 2), nullable=True)

    discount_reason = Column(String(100), nullable=True)

    payment_reference = Column(String(100), nullable=True)

    approved_by_user_id = Column(Integer, ForeignKey("users.id"), nullable=True)
    approved_at = Column(DateTime, nullable=True)

    status = Column(String(30), nullable=False, default="pending")

    created_at = Column(DateTime, server_default=func.now(), nullable=False)

    items = relationship("BookingItem", back_populates="booking")

    # -------------------------------
    # PHASE 8: CREDIT SYSTEM EXTENSION
    # -------------------------------

    billing_mode = Column(String(20), nullable=False, default="prepaid")  # prepaid | credit

    referrer_id = Column(Integer, ForeignKey("referrers.id"), nullable=True)