# -*- coding: utf-8 -*-
# app/services/sas/onboarding.py
"""
SAS Onboarding Service.
Serves structured onboarding content for the first-run experience.
The PySide6 desktop client renders the text and drives pyttsx3 TTS locally.
"""
from __future__ import annotations

from datetime import datetime
from sqlalchemy.orm import Session

from app.services.subscription_service import SubscriptionService


# --------------------------------------------------
# ONBOARDING CONTENT — v2.0
# Each section has:
#   id       → unique key for the desktop to track progress
#   title    → shown as a header in the UI
#   content  → full text rendered in the scroll panel
#   tts_text → what SAS reads aloud (may be shorter/cleaner than content)
#   type     → welcome | terms | whats_new | coming_soon | sas_guide | complete
# --------------------------------------------------

ONBOARDING_SECTIONS = [
    {
        "id": "welcome",
        "type": "welcome",
        "title": "Welcome to LabCore 2.0",
        "content": (
            "Welcome to LabCore 2.0 — a complete reimagining of your laboratory "
            "information system, built from the ground up by Solunex Technologies.\n\n"
            "I am SAS — your Solunex Assistance System. I will be your intelligent "
            "partner throughout every result, every patient, and every decision made "
            "in this laboratory.\n\n"
            "Before we begin, I will guide you through the terms and conditions, "
            "what is new in this version, and how to get the most out of working with me."
        ),
        "tts_text": (
            "Welcome to LabCore 2.0. I am SAS — your Solunex Assistance System. "
            "I will guide you through everything you need to know before we begin."
        ),
        "duration_seconds": 8,
    },
    {
        "id": "terms",
        "type": "terms",
        "title": "Terms and Conditions",
        "content": (
            "BY USING LABCORE 2.0, YOU AGREE TO THE FOLLOWING:\n\n"
            "1. DATA OWNERSHIP\n"
            "All patient data entered into LabCore 2.0 remains the exclusive property "
            "of your laboratory. Solunex Technologies does not access, store, or share "
            "your patient records.\n\n"
            "2. AI-ASSISTED RESULTS\n"
            "SAS provides decision-support suggestions only. All final results must be "
            "reviewed, verified, and authorised by a qualified medical laboratory "
            "scientist. SAS never diagnoses and never replaces professional judgment.\n\n"
            "3. ANONYMIZATION\n"
            "When SAS Tier 2 (Claude AI) is active, patient data is anonymized before "
            "any analysis. Names, phone numbers, and identifiers are never transmitted "
            "to external servers.\n\n"
            "4. SUBSCRIPTION\n"
            "LabCore 2.0 operates on a subscription basis. Feature access is governed "
            "by your current subscription tier. Trial periods are time-limited.\n\n"
            "5. ACCURACY\n"
            "While SAS strives for accuracy in predictions and suggestions, Solunex "
            "Technologies accepts no liability for clinical decisions made based on "
            "AI-assisted suggestions. The laboratory and its qualified staff bear full "
            "professional responsibility for all results issued.\n\n"
            "6. UPDATES\n"
            "Solunex Technologies reserves the right to update, improve, or modify "
            "LabCore at any time. Major changes will be communicated through the "
            "SAS onboarding system."
        ),
        "tts_text": (
            "Please read the terms and conditions carefully. "
            "Key points: your patient data belongs to you and never leaves your system. "
            "SAS is a decision-support tool — all results must be verified by a qualified "
            "medical laboratory scientist. SAS never diagnoses and never replaces your professional judgment."
        ),
        "duration_seconds": 20,
    },
    {
        "id": "whats_new",
        "type": "whats_new",
        "title": "What's New in LabCore 2.0",
        "content": (
            "LabCore 2.0 is a complete platform upgrade. Here is what is new:\n\n"
            "🧠  SAS — SOLUNEX ASSISTANCE SYSTEM\n"
            "An embedded AI that learns from your patient history. SAS predicts likely "
            "result values before you start typing, flags abnormal patterns, and helps "
            "you create professional results faster.\n\n"
            "📁  SSDO — SOLUNEX SMART DATA ORGANIZER\n"
            "Every result, request, and patient profile is automatically classified, "
            "tagged, and grouped. SSDO understands your data so SAS can reason about it.\n\n"
            "🩸  BLOOD BANKING MODULE\n"
            "Full donor management, blood inventory tracking, and cross-match recording "
            "integrated directly into the platform.\n\n"
            "📊  ANALYTICS ENGINE\n"
            "Weekly disease trend reports, severity distribution summaries, and category "
            "breakdowns — all generated automatically from your lab data.\n\n"
            "💳  SUBSCRIPTION SYSTEM\n"
            "Free Trial, Basic, Pro, and Enterprise tiers. Feature access scales with "
            "your subscription. Pro and Enterprise unlock full SAS AI capabilities.\n\n"
            "🔗  UNIFIED PLATFORM\n"
            "Lab App, Cashier App, Admin Panel, and Client Portal — all unified under "
            "a single login with role-based routing.\n\n"
            "📄  PROFESSIONAL REPORTING\n"
            "Result PDFs with embedded QR codes, barcodes, lab branding, and "
            "reference range highlighting — downloadable from both desktop and web."
        ),
        "tts_text": (
            "LabCore 2.0 brings seven major upgrades. "
            "SAS — your Solunex Assistance System — predicts result values and flags patterns. "
            "SSDO automatically organizes and classifies all your data. "
            "Blood Banking, Analytics, Subscription Management, Unified Login, "
            "and Professional Reporting are all new in this version."
        ),
        "duration_seconds": 30,
    },
    {
        "id": "coming_soon",
        "type": "coming_soon",
        "title": "Coming in LabCore 3.0",
        "content": (
            "The following features are in active development for LabCore 3.0:\n\n"
            "🎙️  VOICE RECOGNITION & COMMANDS\n"
            "Speak to SAS directly. Issue commands, ask questions, and receive "
            "spoken analysis — fully hands-free.\n\n"
            "💬  SAS CONVERSATION MODE\n"
            "A full bidirectional conversation interface with SAS. Ask follow-up "
            "questions, request clarifications, and get detailed clinical reasoning "
            "in natural language.\n\n"
            "🌐  MULTI-BRANCH DASHBOARD\n"
            "Aggregate analytics and management across multiple laboratory branches "
            "from a single admin view.\n\n"
            "📱  MOBILE COMPANION APP\n"
            "Access key LabCore functions and receive SAS alerts on your mobile device.\n\n"
            "These features will be delivered as seamless updates. SAS will notify "
            "you when they become available."
        ),
        "tts_text": (
            "Coming in LabCore 3.0: voice recognition so you can speak to SAS directly. "
            "Full conversation mode with bidirectional dialogue. "
            "Multi-branch dashboard and a mobile companion app. "
            "SAS will notify you when these features are available."
        ),
        "duration_seconds": 20,
    },
    {
        "id": "sas_guide",
        "type": "sas_guide",
        "title": "Getting the Most from SAS",
        "content": (
            "SAS becomes smarter the more you use it. Here is how to maximize its value:\n\n"
            "✅  ALWAYS CREATE RESULTS THROUGH LABCORE\n"
            "Every result you enter builds SAS's understanding of your patients. "
            "Results entered outside the system are invisible to SAS and break the "
            "clinical timeline.\n\n"
            "✅  ENTER COMPLETE VALUES\n"
            "SAS predicts based on field history. The more complete your values, "
            "the more accurate SAS's predictions become over time.\n\n"
            "✅  REVIEW SAS SUGGESTIONS — DON'T JUST ACCEPT THEM\n"
            "SAS marks suggestions in a distinct color. Review each one. "
            "Accept what is clinically reasonable, modify what needs adjustment, "
            "and reject what does not fit. Your decisions teach SAS.\n\n"
            "✅  USE THE ASK SAS PANEL\n"
            "The SAS panel on the result creation screen accepts text questions. "
            "Ask SAS to summarize a patient's history, flag concerns, or explain "
            "a trend — at any time during result creation.\n\n"
            "✅  CHECK WEEKLY TRENDS\n"
            "The analytics dashboard shows weekly disease frequency trends. "
            "Review these regularly — SAS uses them to improve its situational "
            "awareness of disease patterns in your patient population.\n\n"
            "SAS is your assistant. The qualified medical laboratory scientist "
            "is always in charge."
        ),
        "tts_text": (
            "Here is how to get the most from SAS. "
            "Always create results through LabCore — every entry makes SAS smarter. "
            "Enter complete values for every field. "
            "Review SAS suggestions carefully — accept, modify, or reject each one. "
            "Use the Ask SAS panel to query patient history at any time. "
            "And check your weekly analytics dashboard regularly. "
            "Remember: SAS is your assistant. You are always in charge."
        ),
        "duration_seconds": 35,
    },
    {
        "id": "complete",
        "type": "complete",
        "title": "You're Ready to Begin",
        "content": (
            "Setup is complete. LabCore 2.0 is ready.\n\n"
            "Your free trial is active. You have full access to all core features "
            "including SAS Tier 1 predictions, SSDO data organization, Blood Banking, "
            "and Analytics.\n\n"
            "Upgrade to Pro or Enterprise at any time to unlock SAS Tier 2 — "
            "full Claude AI integration for deep clinical reasoning and text analysis.\n\n"
            "Welcome to the future of laboratory information management.\n\n"
            "— Solunex Technologies"
        ),
        "tts_text": (
            "Setup is complete. LabCore 2.0 is ready. "
            "Your free trial is active. "
            "Welcome to the future of laboratory information management. "
            "Let us begin."
        ),
        "duration_seconds": 10,
    },
]


VERSION_HISTORY = [
    {
        "version": "2.0.0",
        "release_date": "2026-07-01",
        "highlights": [
            "SAS — Solunex Assistance System (Tier 1 + Tier 2)",
            "SSDO — Solunex Smart Data Organizer",
            "Blood Banking Module",
            "Analytics Engine with weekly disease trends",
            "Subscription and free trial system",
            "Unified 4-in-1 platform (Lab, Cashier, Admin, Portal)",
            "Professional PDF reporting with QR and barcode",
            "Automatic background SSDO indexing and SAS prediction",
        ],
    }
]


class OnboardingService:

    def __init__(self, db):
        self.db = db
        self.subscription_svc = SubscriptionService(db)

    def get_onboarding_content(self) -> dict:
        """
        Returns the full onboarding content package.
        The desktop client renders this and drives TTS locally.
        """
        sub_status = self.subscription_svc.get_subscription_status()
        is_first_run = self.subscription_svc.is_first_run()

        return {
            "is_first_run": is_first_run,
            "version": "2.0.0",
            "generated_at": datetime.utcnow().isoformat(),
            "subscription": {
                "status": sub_status.get("status"),
                "tier": sub_status.get("tier"),
                "tier_display": sub_status.get("tier_display"),
                "expires_at": sub_status.get("expires_at"),
                "is_trial": sub_status.get("is_trial"),
            },
            "sections": ONBOARDING_SECTIONS,
            "version_history": VERSION_HISTORY,
            "total_sections": len(ONBOARDING_SECTIONS),
            "estimated_duration_seconds": sum(
                s["duration_seconds"] for s in ONBOARDING_SECTIONS
            ),
        }

    def complete_onboarding(self) -> dict:
        """
        Marks onboarding as complete.
        Called when the user clicks 'I Understand, Let's Begin'.
        """
        self.subscription_svc.mark_first_run_complete()
        self.subscription_svc.set_config("onboarding_completed_at", datetime.utcnow().isoformat())
        self.subscription_svc.set_config("onboarding_version", "2.0.0")

        return {
            "message": "Onboarding complete. SAS is ready.",
            "first_run": False,
            "completed_at": datetime.utcnow().isoformat(),
        }

    def get_version_history(self) -> list:
        """Returns the full version history for the About / Release Notes screen."""
        return VERSION_HISTORY

    def get_section(self, section_id: str) -> dict:
        """Returns a single onboarding section by id."""
        for section in ONBOARDING_SECTIONS:
            if section["id"] == section_id:
                return section
        return {}