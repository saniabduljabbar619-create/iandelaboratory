# -*- coding: utf-8 -*-
# app/services/sas/patient_analyzer.py
"""
SAS Patient Analyzer.
Builds the clinical profile and field-level history SAS needs
to reason about a patient. Always goes through SSDO's index first
to find which records are relevant, then pulls the raw values
from the actual record via the pointer SSDO stored — the same
way a search index points to a document rather than duplicating it.
"""
from __future__ import annotations

from typing import Optional

from sqlalchemy.orm import Session

from app.models.test_result import TestResult
from app.services.ssdo.query_engine import SSDOQueryEngine


class PatientAnalyzer:

    def __init__(self, db: Session):
        self.db = db
        self.query_engine = SSDOQueryEngine(db)

    def get_field_history(
        self,
        patient_id: int,
        test_category: str,
        field_key: str,
        limit: int = 10,
    ) -> list[dict]:
        """
        Returns chronological (oldest -> newest) historical values
        for one field, drawn from the patient's SSDO-indexed results
        in the same clinical category.
        """
        entries = self.query_engine.get_patient_results_by_category(
            patient_id, test_category, limit=limit
        )
        # query_engine returns newest-first; reverse for chronological order
        entries = list(reversed(entries))

        history: list[dict] = []
        for e in entries:
            record_id = e["record_id"]
            result = self.db.query(TestResult).filter(
                TestResult.id == record_id
            ).first()
            if not result or not isinstance(result.values, dict):
                continue
            if field_key not in result.values:
                continue
            raw = result.values.get(field_key)
            try:
                val = float(raw)
            except (TypeError, ValueError):
                continue
            history.append({"value": val, "date": e["temporal_position"]})

        return history

    def build_patient_profile(self, patient_id: int) -> dict:
        """Full clinical intelligence summary — feeds the SAS UI panel."""
        timeline = self.query_engine.get_patient_timeline(patient_id, limit=20)
        disease_history = self.query_engine.get_patient_disease_history(patient_id)
        critical_history = self.query_engine.get_patient_critical_history(patient_id)

        return {
            "patient_id": patient_id,
            "total_records": len(timeline),
            "disease_history": disease_history,
            "critical_count": len(critical_history),
            "recent_records": timeline[:5],
        }