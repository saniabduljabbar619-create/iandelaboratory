# -*- coding: utf-8 -*-
# app/api/routers/ssdo.py
from __future__ import annotations

from datetime import datetime
from typing import Optional

from fastapi import APIRouter, Depends, BackgroundTasks
from sqlalchemy.orm import Session
from datetime import timedelta, timezone
from app.api.deps import get_db
from app.services.ssdo.query_engine import SSDOQueryEngine
from app.services.ssdo.tasks import (
    index_result_task,
    index_request_task,
    index_patient_task,
)

router = APIRouter(prefix="/api/ssdo", tags=["ssdo"])



def _today_start() -> datetime:
    """Start of today in Nigeria (UTC+1), as naive UTC for DB comparison."""
    tz = timezone(timedelta(hours=1))
    now_local = datetime.now(tz)
    start_local = now_local.replace(hour=0, minute=0, second=0, microsecond=0)
    return start_local.astimezone(timezone.utc).replace(tzinfo=None)

# --------------------------------------------------
# INDEXING ENDPOINTS
# --------------------------------------------------

@router.post("/index/result/{result_id}")
def index_result(result_id: int, background_tasks: BackgroundTasks):
    """Manually trigger SSDO indexing for a test result."""
    background_tasks.add_task(index_result_task, result_id)
    return {"message": f"SSDO indexing queued for result {result_id}."}


@router.post("/index/request/{request_id}")
def index_request(request_id: int, background_tasks: BackgroundTasks):
    """Manually trigger SSDO indexing for a test request."""
    background_tasks.add_task(index_request_task, request_id)
    return {"message": f"SSDO indexing queued for request {request_id}."}


@router.post("/index/patient/{patient_id}")
def index_patient(patient_id: int, background_tasks: BackgroundTasks):
    """Manually trigger SSDO indexing for a patient profile."""
    background_tasks.add_task(index_patient_task, patient_id)
    return {"message": f"SSDO indexing queued for patient {patient_id}."}


# --------------------------------------------------
# QUERY ENDPOINTS
# --------------------------------------------------

@router.get("/patient/{patient_id}/timeline")
def patient_timeline(patient_id: int, limit: int = 50, db: Session = Depends(get_db)):
    engine = SSDOQueryEngine(db)
    return engine.get_patient_timeline(patient_id, limit=limit)


@router.get("/patient/{patient_id}/disease-history")
def patient_disease_history(patient_id: int, db: Session = Depends(get_db)):
    engine = SSDOQueryEngine(db)
    return {"patient_id": patient_id, "disease_history": engine.get_patient_disease_history(patient_id)}


@router.get("/patient/{patient_id}/critical-history")
def patient_critical_history(patient_id: int, db: Session = Depends(get_db)):
    engine = SSDOQueryEngine(db)
    return engine.get_patient_critical_history(patient_id)


@router.get("/patient/{patient_id}/category/{category}")
def patient_results_by_category(patient_id: int, category: str, limit: int = 20, db: Session = Depends(get_db)):
    engine = SSDOQueryEngine(db)
    return engine.get_patient_results_by_category(patient_id, category, limit=limit)


@router.get("/lab/disease-frequency")
def lab_disease_frequency(
    branch_id: Optional[int] = None,
    today: bool = False,
    db: Session = Depends(get_db),
):
    engine = SSDOQueryEngine(db)
    since = _today_start() if today else None
    return engine.get_disease_frequency(branch_id=branch_id, since=since)


@router.get("/lab/severity-summary")
def lab_severity_summary(
    branch_id: Optional[int] = None,
    today: bool = False,
    db: Session = Depends(get_db),
):
    engine = SSDOQueryEngine(db)
    since = _today_start() if today else None
    return engine.get_severity_summary(branch_id=branch_id, since=since)


@router.get("/lab/category-distribution")
def lab_category_distribution(
    branch_id: Optional[int] = None,
    today: bool = False,
    db: Session = Depends(get_db),
):
    engine = SSDOQueryEngine(db)
    since = _today_start() if today else None
    return engine.get_category_distribution(branch_id=branch_id, since=since)