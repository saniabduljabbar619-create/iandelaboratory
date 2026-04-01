from __future__ import annotations

from sqlalchemy import (
    Column,
    Integer,
    String,
    Date,
    Numeric,
    ForeignKey,
    Boolean
)
from sqlalchemy.orm import relationship
from app.db.base import Base


class BookingItem(Base):
    __tablename__ = "booking_items"

    id = Column(Integer, primary_key=True)

    booking_id = Column(Integer, ForeignKey("bookings.id"), nullable=False)

    patient_name = Column(String(255), nullable=False)

    patient_identifier = Column(String(100), nullable=True, index=True)

    patient_id = Column(Integer, nullable=True, index=True)

    patient_phone = Column(String(20), nullable=False)
    dob = Column(Date, nullable=True)
    gender = Column(String(20), nullable=True)

    test_type_id = Column(Integer, ForeignKey("test_types.id"), nullable=False)

    test_name_snapshot = Column(String(255), nullable=False)
    price_snapshot = Column(Numeric(12, 2), nullable=False)

    booking = relationship("Booking", back_populates="items")
    converted = Column(Boolean, default=False, nullable=False)