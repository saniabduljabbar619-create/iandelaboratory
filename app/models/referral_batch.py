# -*- coding: utf-8 -*-
from sqlalchemy import Column, Integer, String, DateTime, func
from app.db.base import Base

class ReferralBatch(Base):
    """The Logistics Envelope for a group of samples from one Referrer."""
    __tablename__ = "referral_batches"

    id = Column(Integer, primary_key=True)
    batch_uid = Column(String(50), unique=True, index=True, nullable=False) # e.g. REF-20260329
    
    referrer_id = Column(Integer, index=True, nullable=False) # Link to your existing referrers table
    
    # Logistics Tracking
    date_received = Column(DateTime, nullable=False)
    date_due = Column(DateTime, nullable=False) # The TAT (Turnaround Time)
    courier_info = Column(String(255), nullable=True)
    
    # Status: 'Pending', 'In-Lab', 'Completed'
    status = Column(String(50), default="Pending", index=True)
    
    created_at = Column(DateTime, server_default=func.now())
    updated_at = Column(DateTime, server_default=func.now(), onupdate=func.now())