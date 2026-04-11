# -*- coding: utf-8 -*-
from __future__ import annotations
import uuid
from sqlalchemy import (
    Column,
    Integer,
    String,
    DateTime,
    Numeric,
    Boolean,
    func,
    UniqueConstraint
)
from app.db.base import Base


class TestType(Base):
    __tablename__ = "test_types"
    __table_args__ = (
        UniqueConstraint("code", name="uq_test_types_code"),
    )

    id = Column(Integer, primary_key=True)
    sync_id = Column(String(36), unique=True, index=True, default=lambda: str(uuid.uuid4()))
    # short code e.g. FBC, LFT, RFT, MAL
    code = Column(String(50), nullable=False, index=True)
    name = Column(String(255), nullable=False, index=True)

    description = Column(String(255), nullable=True)

    # 🔥 REQUIRED FOR BOOKING
    price = Column(Numeric(12, 2), nullable=False)

    # 🔥 REQUIRED FOR CONTROL
    is_active = Column(Boolean, nullable=False, default=True)

    created_at = Column(DateTime, server_default=func.now(), nullable=False)
    updated_at = Column(
        DateTime,
        server_default=func.now(),
        onupdate=func.now(),
        nullable=False
    )
