# -*- coding: utf-8 -*-
# app/utils/lab_report_resolver.py

from sqlalchemy.orm import Session

from app.models.test_result import TestResult
from app.utils.lab_no_generator import next_lab_no


def get_or_create_lab_no(
    db: Session,
    result_id: int,
) -> str:
    """
    Deterministic LAB number resolver.

    Rules:
    - Reuse existing LAB NO if already assigned
    - Generate only once
    - Persist permanently
    """

    result = (
        db.query(TestResult)
        .filter(TestResult.id == int(result_id))
        .first()
    )

    if not result:
        raise ValueError(f"TestResult {result_id} not found")

    existing = (result.lab_no or "").strip()

    # Already assigned → reuse forever
    if existing:
        return existing

    # Generate fresh
    lab_no = next_lab_no(db)

    # Persist permanently
    result.lab_no = lab_no

    db.commit()
    db.refresh(result)

    return lab_no