# -*- coding: utf-8 -*-
# app/services/sas/tier2/anonymizer.py
"""
Strips all PII from patient data before it leaves the local system.
Patient name, phone, address, patient_no — none of it goes to the API.
Only clinical data (age, gender, test values, flags, disease tags) is sent.
"""
from __future__ import annotations

import hashlib
from datetime import date, datetime
from typing import Optional

from app.models.patient import Patient


def anonymize_patient(patient: Patient) -> dict:
    """Returns a PII-free patient descriptor for Claude."""
    anon_ref = hashlib.sha256(
        f"{patient.id}-{patient.branch_id}".encode()
    ).hexdigest()[:12]

    age = None
    if patient.date_of_birth:
        today = date.today()
        dob = patient.date_of_birth
        if isinstance(dob, str):
            dob = date.fromisoformat(dob)
        age = today.year - dob.year - (
            (today.month, today.day) < (dob.month, dob.day)
        )

    return {
        "patient_ref": f"PT-{anon_ref}",
        "age_years": age,
        "gender": patient.gender,
    }


def anonymize_timeline(ssdo_timeline: list[dict]) -> list[dict]:
    """
    Converts the SSDO patient timeline into a Claude-safe
    clinical payload — no record IDs, no patient names,
    no branch references. Pure clinical content only.
    """
    clean: list[dict] = []
    for entry in ssdo_timeline:
        clean.append({
            "date": entry.get("temporal_position"),
            "record_type": entry.get("record_type"),
            "test_category": entry.get("test_category"),
            "disease_tags": entry.get("disease_tags", []),
            "severity_flag": entry.get("severity_flag"),
            "ai_summary": {
                k: v for k, v in (entry.get("ai_summary") or {}).items()
                if k in ("test_code", "flag_count", "status")
            },
        })
    return clean


def build_prediction_payload(
    anon_patient: dict,
    anon_timeline: list[dict],
    current_request: dict,
    format_preference: str = "table",
) -> dict:
    """Full payload sent to Claude for result prediction."""
    return {
        "patient": anon_patient,
        "clinical_timeline": anon_timeline,
        "current_request": current_request,
        "format_preference": format_preference,
        "task": "predict_values_and_suggest_format",
    }


def build_query_payload(
    anon_patient: dict,
    anon_timeline: list[dict],
    question: str,
) -> dict:
    """Payload sent to Claude for a text analysis question."""
    return {
        "patient": anon_patient,
        "clinical_timeline": anon_timeline,
        "question": question,
        "task": "answer_clinical_question",
    }