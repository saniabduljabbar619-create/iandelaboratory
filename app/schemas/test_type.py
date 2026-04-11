# -*- coding: utf-8 -*-
from __future__ import annotations

from datetime import datetime
from pydantic import Field
from app.schemas.common import APIModel


class TestTypeCreate(APIModel):
    code: str = Field(..., min_length=1, max_length=50)
    name: str = Field(..., min_length=1, max_length=255)
    description: str | None = None
    price: float = Field(..., ge=0)
    # ✅ this for the Sync Engine
    sync_id: str | None = Field(default=None, max_length=36)


class TestTypeOut(APIModel):
    id: int
    code: str
    name: str
    description: str | None
    price: float
    created_at: datetime
    updated_at: datetime
