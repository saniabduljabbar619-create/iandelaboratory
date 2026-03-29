# -*- coding: utf-8 -*-
from sqlalchemy import Column, Integer, String, Numeric, Boolean, DateTime, func
from app.db.base import Base

class ReferralLedger(Base):
    """Specific financial records for Referrer Billing."""
    __tablename__ = "referral_ledgers"

    id = Column(Integer, primary_key=True)
    batch_uid = Column(String(50), unique=True, index=True)
    referrer_id = Column(Integer, index=True)
    
    gross_total = Column(Numeric(12, 2), nullable=False)
    discount_percent = Column(Numeric(5, 2), default=0)
    net_payable = Column(Numeric(12, 2), nullable=False)
    
    # Payment Status
    is_settled = Column(Boolean, default=False, index=True) # False = Outstanding Debt
    payment_method = Column(String(50), nullable=True)
    
    created_at = Column(DateTime, server_default=func.now())
    updated_at = Column(DateTime, server_default=func.now(), onupdate=func.now())