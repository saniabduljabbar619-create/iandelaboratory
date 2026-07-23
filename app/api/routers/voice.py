# -*- coding: utf-8 -*-
# app/api/routers/voice.py
"""
Voice announcement API.
The PySide6 desktop polls GET /api/voice/pending on a timer,
speaks each announcement via pyttsx3, then calls
POST /api/voice/{id}/delivered to mark it done.
"""
from __future__ import annotations

from typing import Optional

from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session
from pydantic import BaseModel

from app.api.deps import get_db, get_current_user_claims
from app.services.sas.announcer import AnnouncerService

router = APIRouter(prefix="/api/voice", tags=["voice"])


class ManualAnnouncement(BaseModel):
    message: str
    priority: str = "normal"


def _svc(db: Session, claims: dict) -> AnnouncerService:
    branch_id = claims.get("branch_id") or None
    return AnnouncerService(db, branch_id=branch_id)


@router.get("/pending")
def get_pending(
    limit: int = Query(default=10, le=50),
    db: Session = Depends(get_db),
    claims: dict = Depends(get_current_user_claims),
):
    """
    Returns undelivered announcements ordered by priority then time.
    The PySide6 desktop polls this endpoint every 5-10 seconds.
    Urgent announcements always appear first.
    """
    svc = _svc(db, claims)
    announcements = svc.get_pending(limit=limit)
    return {
        "count": len(announcements),
        "announcements": [
            {
                "id": a.id,
                "type": a.type,
                "title": a.title,
                "voice_text": a.voice_text,
                "priority": a.priority,
                "reference_type": a.reference_type,
                "reference_id": a.reference_id,
                "created_at": a.created_at.isoformat(),
            }
            for a in announcements
        ],
    }


@router.post("/{announcement_id}/delivered")
def mark_delivered(
    announcement_id: int,
    db: Session = Depends(get_db),
    claims: dict = Depends(get_current_user_claims),
):
    """
    Called by the desktop after pyttsx3 finishes speaking the announcement.
    """
    svc = _svc(db, claims)
    success = svc.mark_delivered(announcement_id)
    if not success:
        from fastapi import HTTPException
        raise HTTPException(status_code=404, detail="Announcement not found.")
    return {"message": f"Announcement {announcement_id} marked as delivered."}


@router.post("/delivered/all")
def mark_all_delivered(
    db: Session = Depends(get_db),
    claims: dict = Depends(get_current_user_claims),
):
    """Bulk-mark all pending announcements as delivered. Used on workstation shutdown."""
    svc = _svc(db, claims)
    count = svc.mark_all_delivered()
    return {"message": f"{count} announcement(s) marked as delivered."}


@router.post("/announce")
def manual_announcement(
    payload: ManualAnnouncement,
    db: Session = Depends(get_db),
    claims: dict = Depends(get_current_user_claims),
):
    """
    Admin-triggered manual announcement.
    Useful for lab-wide messages, shift briefings, or system notices.
    """
    svc = _svc(db, claims)
    ann = svc.announce_system(payload.message, payload.priority)
    return {
        "message": "Announcement queued.",
        "announcement_id": ann.id,
        "voice_text": ann.voice_text,
        "priority": ann.priority,
    }


@router.post("/housekeeping")
def housekeeping(
    days: int = Query(default=7),
    db: Session = Depends(get_db),
    claims: dict = Depends(get_current_user_claims),
):
    """Removes delivered announcements older than N days."""
    svc = _svc(db, claims)
    count = svc.clear_old_delivered(days=days)
    return {"message": f"Removed {count} old delivered announcement(s)."}