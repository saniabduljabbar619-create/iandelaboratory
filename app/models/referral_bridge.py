# -*- coding: utf-8 -*-
from sqlalchemy import Column, Integer, String
from app.db.base import Base

class ReferralBridge(Base):
    """Links existing stable Test Requests to a Referral Batch without modifying the core table."""
    __tablename__ = "referral_batch_links"

    id = Column(Integer, primary_key=True)
    batch_uid = Column(String(50), index=True, nullable=False)
    
    # The ID from your stable 'test_requests' table
    test_request_id = Column(Integer, unique=True, nullable=False) 
    
    # Snapshots for fast Lab App viewing without complex joins
    patient_name = Column(String(255)) 
    sample_type = Column(String(100))