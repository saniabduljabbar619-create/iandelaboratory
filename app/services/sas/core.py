# -*- coding: utf-8 -*-
# app/services/sas/core.py
"""
SAS Core — mode dispatcher with Tier 1 → Tier 2 escalation.

Escalation rules (Tier 2 fires when ANY condition is met):
  1. overall_confidence < TIER2_ESCALATION_THRESHOLD
  2. Any field has zero history (no prior data at all)
  3. Caller explicitly requests Tier 2
  4. Subscription tier permits Tier 2 (Pro / Enterprise)
"""
from __future__ import annotations

from sqlalchemy.orm import Session

from app.models.patient import Patient
from app.services.sas.result_predictor import ResultPredictor
from app.services.sas.patient_analyzer import PatientAnalyzer
from app.services.sas.text_query import TextQueryService
from app.services.sas.tier2.anonymizer import (
    anonymize_patient,
    anonymize_timeline,
    build_prediction_payload,
)
from app.services.sas.tier2.claude_client import call_predict
from app.services.sas.tier2.response_parser import parse_prediction_response
from app.services.ssdo.query_engine import SSDOQueryEngine
from app.services.subscription_service import SubscriptionService

TIER2_ESCALATION_THRESHOLD = 60   # overall_confidence below this → escalate
TIER2_ZERO_HISTORY_THRESHOLD = 1  # escalate if any field has fewer than this many history points


class SASCore:

    def __init__(self, db: Session):
        self.db = db
        self.predictor = ResultPredictor(db)
        self.analyzer = PatientAnalyzer(db)
        self.query_engine = SSDOQueryEngine(db)
        self.text_query = TextQueryService(db)

    # --------------------------------------------------
    # RESULT PREDICTION — TIER 1 + OPTIONAL TIER 2
    # --------------------------------------------------

    def predict_result(
        self,
        patient_id: int,
        test_type_id: int,
        template_snapshot: dict,
        force_tier2: bool = False,
    ) -> dict:
        # Always run Tier 1 first — it's fast, free, and offline-safe
        tier1_result = self.predictor.predict_for_template(
            patient_id, test_type_id, template_snapshot
        )

        # Decide whether to escalate
        should_escalate = self._should_escalate(tier1_result, force_tier2)

        if not should_escalate:
            tier1_result["tier2_attempted"] = False
            return tier1_result

        # Check subscription permits Tier 2
        if not self._subscription_allows_tier2():
            tier1_result["tier2_attempted"] = False
            tier1_result["tier2_blocked"] = "Tier 2 requires Pro or Enterprise subscription."
            return tier1_result

        # Build anonymized payload and call Claude
        patient = self.db.query(Patient).filter(Patient.id == patient_id).first()
        if not patient:
            tier1_result["tier2_attempted"] = False
            return tier1_result

        timeline = self.query_engine.get_patient_timeline(patient_id, limit=20)
        anon_patient = anonymize_patient(patient)
        anon_timeline = anonymize_timeline(timeline)

        current_request = {
            "test_type_id": test_type_id,
            "test_code": tier1_result.get("test_code"),
            "test_category": tier1_result.get("test_category"),
            "fields": [
                {
                    "key": f["key"],
                    "label": f.get("label"),
                    "unit": f.get("unit"),
                    "reference_range": {"low": None, "high": None},
                }
                for f in tier1_result.get("fields", [])
            ],
        }

        payload = build_prediction_payload(
            anon_patient, anon_timeline, current_request
        )
        claude_response = call_predict(payload)

        return parse_prediction_response(claude_response, tier1_result)

    # --------------------------------------------------
    # TEXT QUERIES
    # --------------------------------------------------

    def query_patient(self, patient_id: int, question: str) -> dict:
        """On-demand clinical question about a specific patient."""
        return self.text_query.query_patient(patient_id, question)

    def query_lab(self, question: str, branch_id: int = None) -> dict:
        """Lab-wide analysis question — population level, no patient PII."""
        return self.text_query.query_lab(question, branch_id=branch_id)

    # --------------------------------------------------
    # PATIENT PROFILE
    # --------------------------------------------------

    def get_patient_profile(self, patient_id: int) -> dict:
        return self.analyzer.build_patient_profile(patient_id)

    # --------------------------------------------------
    # INTERNAL HELPERS
    # --------------------------------------------------

    def _should_escalate(self, tier1_result: dict, force_tier2: bool) -> bool:
        if force_tier2:
            return True
        if tier1_result.get("overall_confidence", 100) < TIER2_ESCALATION_THRESHOLD:
            return True
        # Escalate if any field has very little history
        for f in tier1_result.get("fields", []):
            if f.get("history_count", 99) < TIER2_ZERO_HISTORY_THRESHOLD:
                return True
        return False

    def _subscription_allows_tier2(self) -> bool:
        try:
            svc = SubscriptionService(self.db)
            return svc.can_use_ai_tier2()
        except Exception:
            return False