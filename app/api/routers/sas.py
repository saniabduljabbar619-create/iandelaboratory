# -*- coding: utf-8 -*-
# app/api/routers/sas.py
from __future__ import annotations

from typing import Any, Optional

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session
from pydantic import BaseModel

from app.api.deps import get_db, get_current_user_claims
from app.services.sas.core import SASCore

router = APIRouter(prefix="/api/sas", tags=["sas"])


# --------------------------------------------------
# SCHEMAS
# --------------------------------------------------

class PredictRequest(BaseModel):
    patient_id: int
    test_type_id: int
    template_snapshot: dict[str, Any]
    force_tier2: bool = False


class PatientQueryRequest(BaseModel):
    question: str


class LabQueryRequest(BaseModel):
    question: str
    branch_id: Optional[int] = None


# --------------------------------------------------
# ENDPOINTS
# --------------------------------------------------

@router.post("/predict")
def predict_result(
    payload: PredictRequest,
    db: Session = Depends(get_db),
    claims: dict = Depends(get_current_user_claims),
):
    """
    SAS prediction endpoint.
    Tier 1 (rule-based) always runs first.
    Escalates to Tier 2 (Claude API) automatically when:
      - overall confidence < 60%
      - any field has no prior history
      - force_tier2 = true (explicit override)
    Tier 2 requires Pro or Enterprise subscription.
    """
    core = SASCore(db)
    return core.predict_result(
        patient_id=payload.patient_id,
        test_type_id=payload.test_type_id,
        template_snapshot=payload.template_snapshot,
        force_tier2=payload.force_tier2,
    )


@router.get("/patient/{patient_id}/profile")
def get_patient_profile(
    patient_id: int,
    db: Session = Depends(get_db),
    claims: dict = Depends(get_current_user_claims),
):
    """Returns the SAS clinical intelligence summary for a patient."""
    core = SASCore(db)
    return core.get_patient_profile(patient_id)


@router.post("/patient/{patient_id}/query")
def query_patient(
    patient_id: int,
    payload: PatientQueryRequest,
    db: Session = Depends(get_db),
    claims: dict = Depends(get_current_user_claims),
):
    """
    SAS Mode 5 — on-demand text analysis for a specific patient.
    Ask SAS any clinical question about this patient's history.
    Powered by Claude API. Requires Pro or Enterprise subscription.
    Examples:
      - 'Summarize this patient's haematology trend over the last 3 visits'
      - 'What disease patterns does SAS detect in this patient?'
      - 'Are there any critical values I should flag to the doctor?'
    """
    core = SASCore(db)
    return core.query_patient(patient_id, payload.question)


@router.post("/lab/query")
def query_lab(
    payload: LabQueryRequest,
    db: Session = Depends(get_db),
    claims: dict = Depends(get_current_user_claims),
):
    """
    SAS lab-wide analysis — population level, no patient PII.
    Ask SAS questions about the lab's overall data patterns.
    Examples:
      - 'What is the most common disease pattern this week?'
      - 'Which test category has the highest abnormal rate?'
      - 'Are there any emerging disease trends I should be aware of?'
    """
    core = SASCore(db)
    return core.query_lab(payload.question, branch_id=payload.branch_id)