from sqlalchemy import Column, BigInteger, String, DateTime, Text
from sqlalchemy.sql import func

from app.db.base import Base


class PaymentProof(Base):

    __tablename__ = "payment_proofs"

    id = Column(BigInteger, primary_key=True)

    booking_id = Column(BigInteger, nullable=False)

    file_path = Column(String(255), nullable=False)

    status = Column(String(20), default="pending")

    uploaded_at = Column(DateTime, server_default=func.now())

    verified_by = Column(BigInteger)

    verified_at = Column(DateTime)

    note = Column(Text)