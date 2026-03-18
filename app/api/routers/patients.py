# app/api/routers/patients.py

from __future__ import annotations

from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session
from typing import Optional

from app.api.deps import get_db
from app.core.dependencies import get_current_user
from app.models.user import User
from app.schemas.patient import PatientCreate, PatientUpdate, PatientOut
from app.services.patient_service import PatientService

router = APIRouter()


@router.post("", response_model=PatientOut)
def create_patient(
    payload: PatientCreate,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    service = PatientService(db, current_user)
    return service.create(payload)


@router.get("/search", response_model=list[PatientOut])
def search_patients(
    q: str = Query(..., min_length=1),
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    service = PatientService(db, current_user)
    return service.search(q)


@router.get("/{patient_id}", response_model=PatientOut)
def get_patient(
    patient_id: int,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    service = PatientService(db, current_user)
    return service.get(patient_id)


@router.patch("/{patient_id}", response_model=PatientOut)
def update_patient(
    patient_id: int,
    payload: PatientUpdate,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    service = PatientService(db, current_user)
    return service.update(patient_id, payload)