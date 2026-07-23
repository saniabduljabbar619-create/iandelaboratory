# -*- coding: utf-8 -*-
# app/services/sas/text_query.py
"""
SAS Mode 5 — On-demand text analysis.
The scientist types a question, SAS answers using the patient's
SSDO-derived history fed through Claude API.
Text only in v2.0. Voice query comes in v3.0.
"""
from __future__ import annotations

from sqlalchemy.orm import Session

from app.models.patient import Patient
from app.services.ssdo.query_engine import SSDOQueryEngine
from app.services.sas.tier2.anonymizer import anonymize_patient, anonymize_timeline, build_query_payload
from app.services.sas.tier2.claude_client import call_text_query, call_lab_analysis
from app.services.sas.tier2.response_parser import parse_query_response


class TextQueryService:

    def __init__(self, db: Session):
        self.db = db
        self.query_engine = SSDOQueryEngine(db)

    def query_patient(self, patient_id: int, question: str) -> dict:
        """
        Answer a clinical question about a specific patient
        using their full SSDO timeline as context.
        """
        patient = self.db.query(Patient).filter(
            Patient.id == patient_id
        ).first()

        if not patient:
            return {
                "answer": f"Patient {patient_id} not found.",
                "key_findings": [],
                "recommendations": [],
                "confidence": 0,
                "caveat": "Patient record not found in the system.",
                "tier_used": 0,
            }

        timeline = self.query_engine.get_patient_timeline(patient_id, limit=30)
        anon_patient = anonymize_patient(patient)
        anon_timeline = anonymize_timeline(timeline)

        payload = build_query_payload(anon_patient, anon_timeline, question)
        raw_response = call_text_query(payload)

        return parse_query_response(raw_response)

    def query_lab(self, question: str, branch_id: int = None) -> dict:
        """
        Answer a lab-wide analysis question using aggregated SSDO data.
        No patient-specific data — population-level only.
        """
        disease_freq = self.query_engine.get_disease_frequency(branch_id=branch_id, limit=20)
        severity_summary = self.query_engine.get_severity_summary(branch_id=branch_id)
        category_dist = self.query_engine.get_category_distribution(branch_id=branch_id)

        context = {
            "disease_frequency": disease_freq,
            "severity_distribution": severity_summary,
            "test_category_distribution": category_dist,
        }

        raw_response = call_lab_analysis(question, context)
        return parse_query_response(raw_response)