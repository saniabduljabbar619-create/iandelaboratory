# -*- coding: utf-8 -*-
from __future__ import annotations

from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session

from app.api.deps import get_db
from app.schemas.test_template import TestTemplateCreate, TestTemplateOut
from app.services.template_service import TemplateService

router = APIRouter()


@router.post("", response_model=TestTemplateOut)
def create_template(payload: TestTemplateCreate, db: Session = Depends(get_db)):
    return TemplateService(db).create(payload)


@router.get("/active", response_model=list[TestTemplateOut])
def list_active_templates(
    test_type_id: int | None = Query(default=None),
    db: Session = Depends(get_db),
):
    return TemplateService(db).list_active(test_type_id=test_type_id)


@router.get("/{template_id}", response_model=TestTemplateOut)
def get_template(template_id: int, db: Session = Depends(get_db)):
    return TemplateService(db).get(template_id)
