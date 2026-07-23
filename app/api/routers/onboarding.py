# -*- coding: utf-8 -*-
# app/api/routers/onboarding.py
from __future__ import annotations

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.api.deps import get_db
from app.services.sas.onboarding import OnboardingService

router = APIRouter(prefix="/api/onboarding", tags=["onboarding"])


@router.get("/content")
def get_onboarding_content(db: Session = Depends(get_db)):
    """
    Returns the full structured onboarding content package.
    The PySide6 desktop client renders this and drives pyttsx3 TTS locally.
    Called on every app launch — returns is_first_run flag so the
    desktop knows whether to show the full screen or skip it.
    """
    svc = OnboardingService(db)
    return svc.get_onboarding_content()


@router.post("/complete")
def complete_onboarding(db: Session = Depends(get_db)):
    """
    Marks onboarding as complete.
    Called when the user clicks 'I Understand, Let's Begin'.
    Sets SystemConfig first_run = false permanently.
    Can only be re-triggered from Admin Panel → Settings → SAS → Replay Onboarding.
    """
    svc = OnboardingService(db)
    return svc.complete_onboarding()


@router.post("/reset")
def reset_onboarding(db: Session = Depends(get_db)):
    """
    Admin-only reset — replays onboarding on next launch.
    Accessible from Admin Panel → Settings → SAS → Replay Onboarding.
    """
    svc = OnboardingService(db)
    svc.subscription_svc.set_config("first_run", "true")
    return {"message": "Onboarding reset. Will replay on next application launch."}


@router.get("/section/{section_id}")
def get_section(section_id: str, db: Session = Depends(get_db)):
    """Returns a single onboarding section by id."""
    svc = OnboardingService(db)
    section = svc.get_section(section_id)
    if not section:
        from fastapi import HTTPException
        raise HTTPException(status_code=404, detail=f"Section '{section_id}' not found.")
    return section


@router.get("/version-history")
def get_version_history(db: Session = Depends(get_db)):
    """Returns the full version history for the About / Release Notes screen."""
    svc = OnboardingService(db)
    return svc.get_version_history()