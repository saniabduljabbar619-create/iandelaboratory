# -*- coding: utf-8 -*-
# app/api/routers/test_requests.py

from __future__ import annotations

from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session
from typing import Optional

from app.api.deps import get_db
from app.core.dependencies import get_current_user
from app.models.user import User
from app.schemas.test_request import (
    TestRequestCreate,
    TestRequestOut,
    TestRequestStatusUpdate,
)
from app.services.test_request_service import TestRequestService

router = APIRouter()


@router.post("", response_model=TestRequestOut)
def create_test_request(
    payload: TestRequestCreate,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    service = TestRequestService(db, current_user)
    return service.create(payload)


@router.get("")
def list_test_requests(
    status: Optional[str] = Query(default=None),
    patient_id: Optional[int] = Query(default=None),
    limit: int = Query(default=50, ge=1, le=200),
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    service = TestRequestService(db, current_user)
    return service.list(
        status=status,
        patient_id=patient_id,
        limit=limit,
    )


@router.patch("/{request_id}/status", response_model=TestRequestOut)
def update_test_request_status(
    request_id: int,
    payload: TestRequestStatusUpdate,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    service = TestRequestService(db, current_user)
    return service.update_status(request_id, payload)