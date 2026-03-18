# -*- coding: utf-8 -*-
from __future__ import annotations

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.api.deps import get_db
from app.schemas.test_type import TestTypeCreate, TestTypeOut
from app.services.test_type_service import TestTypeService

router = APIRouter()


@router.post("", response_model=TestTypeOut)
def create_test_type(payload: TestTypeCreate, db: Session = Depends(get_db)):
    return TestTypeService(db).create(payload)

@router.patch("/{test_type_id}", response_model=TestTypeOut)
def update_test_type(
    test_type_id: int,
    payload: TestTypeCreate,
    db: Session = Depends(get_db),
):
    return TestTypeService(db).update(test_type_id, payload)

@router.get("", response_model=list[TestTypeOut])
def list_test_types(db: Session = Depends(get_db)):
    return TestTypeService(db).list()
