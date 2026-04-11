# -*- coding: utf-8 -*-
from __future__ import annotations
from typing import Any, Dict, List

from datetime import datetime
from typing import List

from pydantic import Field
from app.schemas.common import APIModel


class ResultInstantiate(APIModel):
    patient_id: int
    test_type_id: int
    template_id: int | None
    sync_id: str | None = Field(default=None, max_length=36)

class ResultUpdateValues(APIModel):
    values: dict = Field(default_factory=dict)
    notes: str | None = None


class ResultSetStatus(APIModel):
    status: str = Field(..., min_length=1)


class TestResultOut(APIModel):
    id: int
    sync_id: str | None
    patient_id: int
    test_type_id: int
    template_id: int | None
    status: str
    template_snapshot: Dict[str, Any]
    values: Dict[str, Any]
    flags: Dict[str, Any]
    notes: str | None
    created_at: datetime
    updated_at: datetime


class PagedTestResultOut(APIModel):
    value: List[TestResultOut]
    Count: int
    

class ResultInstantiateFromSnapshot(APIModel):
    patient_id: int
    test_type_id: int
    template_id: int | None = None  # optional provenance
    template_snapshot: Dict[str, Any] = Field(default_factory=dict)
    values: Dict[str, Any] = Field(default_factory=dict)
    notes: str | None = None
    sync_id: str | None = Field(default=None, max_length=36)
    branch_id: int | None = None 
    # Optional: also add status if you want to sync pre-released results
    status: str | None = None
