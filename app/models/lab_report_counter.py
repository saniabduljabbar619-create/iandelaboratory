# -*- coding: utf-8 -*-
# app/models/lab_report_counter.py

from datetime import datetime, timezone

from sqlalchemy import Column, Integer, DateTime

from app.db.base import Base


class LabReportCounter(Base):
    __tablename__ = "lab_report_counters"

    id = Column(Integer, primary_key=True, index=True)

    # Example: 26, 27, 28
    year = Column(Integer, nullable=False, unique=True)

    # Last used report number for that year
    last_number = Column(Integer, nullable=False, default=0)

    updated_at = Column(
        DateTime(timezone=True),
        default=lambda: datetime.now(timezone.utc),
        onupdate=lambda: datetime.now(timezone.utc),
    )