# -*- coding: utf-8 -*-
from __future__ import annotations

from fastapi import HTTPException
from sqlalchemy.orm import Session

from app.models.test_template import TestTemplate
from app.schemas.test_template import TestTemplateCreate


class TemplateService:
    def __init__(self, db: Session):
        self.db = db

    def create(self, payload: TestTemplateCreate) -> TestTemplate:
        t = TestTemplate(**payload.model_dump())
        self.db.add(t)
        self.db.commit()
        self.db.refresh(t)
        return t

    def get(self, template_id: int) -> TestTemplate:
        t = self.db.query(TestTemplate).filter(TestTemplate.id == template_id).first()
        if not t:
            raise HTTPException(status_code=404, detail="Template not found")
        return t

    def list_active(self, test_type_id: int | None = None) -> list[TestTemplate]:
        q = self.db.query(TestTemplate).filter(TestTemplate.is_active == True)  # noqa: E712
        if test_type_id:
            q = q.filter(TestTemplate.test_type_id == test_type_id)
        return q.order_by(TestTemplate.id.desc()).limit(100).all()
