# -*- coding: utf-8 -*-
from __future__ import annotations
import uuid
from sqlalchemy import Column, Integer, String, DateTime, Numeric, Boolean, func, ForeignKey, Enum
from sqlalchemy.orm import relationship, Mapped, mapped_column
from app.db.base import Base

# ==============================================================
# 1. REFERRAL STORE (The "History Authority")
# ==============================================================
class ReferralStore(Base):
    """Immutable archive of the referral event as reported by the Cashier."""
    __tablename__ = "referral_store"

    id = Column(Integer, primary_key=True, autoincrement=True)
    sync_id = Column(String(36), unique=True, index=True, default=lambda: str(uuid.uuid4()))
    
    # Unified Fingerprint (SLB-BKG-XXXX)
    batch_code = Column(String(50), nullable=False, index=True)

    # Facility & Clinician Snapshots (Never changes even if profiles do)
    facility_name = Column(String(255), nullable=False, index=True)
    facility_phone = Column(String(30), nullable=False) # 🔒 Required snapshot
    facility_address = Column(String(500), nullable=True)
    clinician_name = Column(String(255), nullable=True) # 🔒 Required snapshot
    
    # Patient Snapshot at time of entry
    patient_name_snapshot = Column(String(255), nullable=False)
    patient_phone_snapshot = Column(String(30), nullable=False)
    
    # Clinical Intent
    test_types_csv = Column(String(500), nullable=False) # e.g., "MAL, FBC, LFT"
    sample_type = Column(String(100), nullable=True)     # e.g., "Blood", "Urine"
    
    created_at = Column(DateTime, server_default=func.now(), nullable=False)
    branch_id = Column(Integer, nullable=False, index=True)

# ==============================================================
# 2. REFERRALS DATA (The "Clinical Bridge")
# ==============================================================
class ReferralData(Base):
    """Manages the conversion state between the Store and the Clinical Engine."""
    __tablename__ = "referral_data"

    id = Column(Integer, primary_key=True)
    sync_id = Column(String(36), unique=True, index=True, default=lambda: str(uuid.uuid4()))
    
    # Link back to the Archive
    store_id: Mapped[int] = mapped_column(ForeignKey("referral_store.id"), nullable=False)
    
    # Biological / Conversion Info
    # Storing bio info here separately ensures clinical 'drifting' doesn't touch the Store
    bio_gender = Column(String(20), nullable=True)
    bio_dob = Column(DateTime, nullable=True)
    
    # Authority Link: NULL until the 'Conversion' button is clicked
    patient_id: Mapped[int] = mapped_column(ForeignKey("patients.id"), nullable=True)
    test_request_id: Mapped[int] = mapped_column(ForeignKey("test_requests.id"), nullable=True)
    
    status = Column(
        Enum("pending", "converted", "rejected", name="referral_data_status"),
        server_default="pending",
        nullable=False
    )
    
    created_at = Column(DateTime, server_default=func.now())
    
    # Relationships
    store = relationship("ReferralStore")
    patient = relationship("Patient")

# ==============================================================
# 3. REFERRAL FINANCIAL RECORD (The "Wealth Ledger")
# ==============================================================
class ReferralFinancialRecord(Base):
    """The absolute authority for Referrer money, discounts, and payments."""
    __tablename__ = "referral_financial_records"

    id = Column(Integer, primary_key=True)
    sync_id = Column(String(36), unique=True, index=True, default=lambda: str(uuid.uuid4()))
    
    # Link via the Unified Code
    batch_code = Column(String(50), nullable=False, index=True)
    referrer_id = Column(Integer, nullable=False, index=True) # ID from your Referrers table
    
    # Economic Data
    gross_total = Column(Numeric(12, 2), nullable=False)
    discount_percent = Column(Numeric(5, 2), server_default="0.00")
    net_payable = Column(Numeric(12, 2), nullable=False)
    
    is_settled = Column(Boolean, default=False, nullable=False)
    
    # Link to the actual Payment transaction (Authority check)
    payment_id: Mapped[int] = mapped_column(ForeignKey("payments.id"), nullable=True)
    
    created_at = Column(DateTime, server_default=func.now())
    
    # Relationships
    payment = relationship("Payment")
