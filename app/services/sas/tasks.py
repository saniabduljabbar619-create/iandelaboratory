# -*- coding: utf-8 -*-
# app/services/sas/tasks.py
"""
Background-safe SAS task wrappers.
Generates Tier 1 predictions for a freshly created result and
stores them on the record itself — sas_predictions / sas_confidence.
Opens its own DB session, same rationale as ssdo/tasks.py.
"""
from __future__ import annotations

from app.db.session import SessionLocal
from app.models.test_result import TestResult
from app.services.sas.core import SASCore


def generate_predictions_task(result_id: int) -> None:
    db = SessionLocal()
    try:
        result = db.query(TestResult).filter(TestResult.id == result_id).first()
        if not result:
            return

        core = SASCore(db)
        outcome = core.predict_result(
            patient_id=result.patient_id,
            test_type_id=result.test_type_id,
            template_snapshot=result.template_snapshot or {},
        )

        result.sas_predictions = outcome.get("predictions", {})
        result.sas_confidence = outcome.get("confidence_per_field", {})
        db.commit()
    except Exception as exc:
        print(f"[SAS] Failed to generate predictions for result {result_id}: {exc}")
        db.rollback()
    finally:
        db.close()