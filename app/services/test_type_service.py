# -*- coding: utf-8 -*-
from __future__ import annotations

from fastapi import HTTPException
from sqlalchemy.orm import Session

from app.models.test_type import TestType
from app.schemas.test_type import TestTypeCreate


class TestTypeService:
    def __init__(self, db: Session):
        self.db = db

    def create(self, payload: TestTypeCreate) -> TestType:
        exists = self.db.query(TestType).filter(TestType.code == payload.code).first()
        if exists:
            raise HTTPException(status_code=400, detail="Test type code already exists")
        t = TestType(**payload.model_dump())
        self.db.add(t)
        self.db.commit()
        self.db.refresh(t)
        return t

    def list(self) -> list[TestType]:
        return (
            self.db.query(TestType)
            .order_by(TestType.id.desc())
            .limit(200)
            .all()
        )
    

    def update(self, test_type_id: int, payload: TestTypeCreate) -> TestType:

        t = self.db.query(TestType).filter(TestType.id == test_type_id).first()

        if not t:
            raise HTTPException(status_code=404, detail="Test type not found")

        # ensure code uniqueness
        if payload.code != t.code:
            exists = (
                self.db.query(TestType)
                .filter(TestType.code == payload.code)
                .first()
            )
            if exists:
                raise HTTPException(status_code=400, detail="Test type code already exists")

        t.code = payload.code
        t.name = payload.name
        t.description = payload.description
        t.price = payload.price

        self.db.commit()
        self.db.refresh(t)

        return t

    def list_active(self) -> list[TestType]:
        return (
            self.db.query(TestType)
            .filter(TestType.is_active == True)
            .order_by(TestType.name.asc())
            .all()
        )