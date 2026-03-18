# -*- coding: utf-8 -*-
from __future__ import annotations

from datetime import datetime
from pydantic import Field
from app.schemas.common import APIModel


class TestTemplateCreate(APIModel):
    test_type_id: int
    title: str = Field(..., min_length=1, max_length=255)
    structure: dict
    rules: dict | None = None
    is_active: bool = True


class TestTemplateOut(APIModel):
    id: int
    test_type_id: int
    title: str
    structure: dict
    rules: dict | None
    is_active: bool
    created_at: datetime
    updated_at: datetime
