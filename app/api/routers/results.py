# -*- coding: utf-8 -*-
# app/api/routers/results.py
from __future__ import annotations

from typing import Optional

from fastapi import APIRouter, Depends, Header, Query
from sqlalchemy.orm import Session

from app.api.deps import get_db
from app.core.dependencies import get_current_user  # ← REQUIRED

from app.schemas.test_result import (
    ResultInstantiate,
    ResultUpdateValues,
    ResultSetStatus,
    TestResultOut,
    PagedTestResultOut,
    ResultInstantiateFromSnapshot,
)

from app.services.result_service import ResultService

router = APIRouter()


@router.post("/instantiate", response_model=TestResultOut)
def instantiate_result(
    payload: ResultInstantiate,
    current_user = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    service = ResultService(db, current_user)
    return service.instantiate(payload)


@router.post("/from-snapshot", response_model=TestResultOut)
def instantiate_from_snapshot(
    payload: ResultInstantiateFromSnapshot,
    current_user = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    service = ResultService(db, current_user)
    return service.instantiate_from_snapshot(payload)


@router.get("/{result_id}", response_model=TestResultOut)
def get_result(
    result_id: int,
    current_user = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    service = ResultService(db, current_user)
    return service.get(result_id)


@router.patch("/{result_id}/values", response_model=TestResultOut)
def update_result_values(
    result_id: int,
    payload: ResultUpdateValues,
    current_user = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    service = ResultService(db, current_user)
    return service.update_values(result_id, payload)


@router.patch("/{result_id}/status", response_model=TestResultOut)
def set_result_status(
    result_id: int,
    payload: ResultSetStatus,
    current_user = Depends(get_current_user),
    db: Session = Depends(get_db),
    x_role: str = Header(default="labtech"),
):
    service = ResultService(db, current_user)
    return service.set_status(result_id, payload.status, role=x_role)


@router.get("", response_model=PagedTestResultOut)
def list_results(
    current_user = Depends(get_current_user),
    db: Session = Depends(get_db),
    patient_id: Optional[int] = Query(default=None),
    status: Optional[str] = Query(default=None),
    limit: int = Query(default=50, ge=1, le=200),
    offset: int = Query(default=0, ge=0),
    x_role: str = Header(default="labtech"),
):
    service = ResultService(db, current_user)
    rows, total = service.list(
        patient_id=patient_id,
        status=status,
        limit=limit,
        offset=offset,
        role=x_role,
    )
    return {"value": rows, "Count": total}
