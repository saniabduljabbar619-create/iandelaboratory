from sqlalchemy import Column, BigInteger, String, Boolean, Text, DateTime
from sqlalchemy.sql import func

from app.db.base import Base


class Notification(Base):

    __tablename__ = "notifications"

    id = Column(BigInteger, primary_key=True, index=True)

    type = Column(String(50), nullable=False)

    reference_type = Column(String(50))
    reference_id = Column(BigInteger)

    title = Column(String(255), nullable=False)
    message = Column(Text)

    is_read = Column(Boolean, default=False)

    created_at = Column(DateTime, server_default=func.now())