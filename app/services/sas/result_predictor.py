# -*- coding: utf-8 -*-
# app/services/sas/result_predictor.py
"""
SAS Result Predictor — orchestrates Tier 1 prediction across every
field in a result template, using the patient's SSDO-derived history.
"""
from __future__ import annotations

from typing import Any

from sqlalchemy.orm import Session

from app.models.test_type import TestType
from app.services.ssdo.classifier import classify_test_category
from app.services.sas.patient_analyzer import PatientAnalyzer
from app.services.sas.tier1.rule_engine import predict_field_value, flag_predicted_value


class ResultPredictor:

    def __init__(self, db: Session):
        self.db = db
        self.analyzer = PatientAnalyzer(db)

    def predict_for_template(
        self,
        patient_id: int,
        test_type_id: int,
        template_snapshot: dict,
    ) -> dict:
        test_type = self.db.query(TestType).filter(
            TestType.id == test_type_id
        ).first()
        test_code = test_type.code if test_type else ""
        category = classify_test_category(test_code)

        fields = self._extract_fields(template_snapshot)

        predictions: dict[str, Any] = {}
        confidences: dict[str, int] = {}
        field_details: list[dict] = []

        for f in fields:
            key = f.get("key")
            if not key:
                continue
            ref = f.get("ref") or {}
            low = ref.get("low")
            high = ref.get("high")

            history = self.analyzer.get_field_history(patient_id, category, key)
            outcome = predict_field_value(history)
            predicted_value = outcome["predicted_value"]
            predicted_flag = (
                flag_predicted_value(predicted_value, low, high)
                if predicted_value is not None
                else "unknown"
            )

            predictions[key] = predicted_value
            confidences[key] = outcome["confidence"]

            field_details.append({
                "key": key,
                "label": f.get("label", key),
                "unit": f.get("unit"),
                "predicted_value": predicted_value,
                "confidence": outcome["confidence"],
                "trend_direction": outcome["trend_direction"],
                "predicted_flag": predicted_flag,
                "basis": outcome["basis"],
                "history_count": len(history),
            })

        overall_confidence = (
            round(sum(confidences.values()) / len(confidences), 1)
            if confidences else 0
        )

        return {
            "patient_id": patient_id,
            "test_type_id": test_type_id,
            "test_code": test_code,
            "test_category": category,
            "predictions": predictions,
            "confidence_per_field": confidences,
            "overall_confidence": overall_confidence,
            "fields": field_details,
            "tier_used": 1,
        }

    def _extract_fields(self, snapshot: dict) -> list[dict]:
        """Mirrors ComputeService's field extraction so SAS reads the same shapes."""
        fields = snapshot.get("fields")
        if isinstance(fields, list):
            return [f for f in fields if isinstance(f, dict)]

        out: list[dict] = []
        sections = snapshot.get("sections")
        if isinstance(sections, list):
            for s in sections:
                if isinstance(s, dict) and isinstance(s.get("fields"), list):
                    out.extend([f for f in s["fields"] if isinstance(f, dict)])
        return out