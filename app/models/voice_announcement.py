# -*- coding: utf-8 -*-
# app/models/voice_announcement.py
from __future__ import annotations

from sqlalchemy import Column, Integer, String, Text, Boolean, DateTime, func
from app.db.base import Base


class VoiceAnnouncement(Base):
    """
    Voice announcement queue.
    Backend generates entries; PySide6 desktop polls, speaks via pyttsx3,
    then marks delivered. Each workstation polls independently.
    """
    __tablename__ = "voice_announcements"

    id = Column(Integer, primary_key=True)

    type = Column(String(50), nullable=False, index=True)
    # new_request | critical_result | abnormal_result |
    # analysis_summary | sas_suggestion | system

    title = Column(String(255), nullable=False)
    voice_text = Column(Text, nullable=False)

    priority = Column(String(20), nullable=False, default="normal")
    # urgent | normal | low

    # Optional link back to the triggering record
    reference_type = Column(String(50), nullable=True)
    reference_id = Column(Integer, nullable=True)

    branch_id = Column(Integer, nullable=True, index=True)

    is_delivered = Column(Boolean, default=False, nullable=False, index=True)
    delivered_at = Column(DateTime, nullable=True)

    created_at = Column(DateTime, server_default=func.now(), nullable=False)