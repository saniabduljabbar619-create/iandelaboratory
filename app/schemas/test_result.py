# -*- coding: utf-8 -*-
from __future__ import annotations
from typing import Any, Dict, List, Optional

from datetime import datetime
from pydantic import Field
from app.schemas.common import APIModel


class ResultInstantiate(APIModel):
    patient_id: int
    test_type_id: int
    template_id: Optional[int] = None
    sync_id: Optional[str] = Field(default=None, max_length=36)


class ResultUpdateValues(APIModel):
    values: dict = Field(default_factory=dict)
    notes: Optional[str] = None


class ResultSetStatus(APIModel):
    status: str = Field(..., min_length=1)


class TestResultOut(APIModel):
    id: int
    sync_id: Optional[str] = None
    patient_id: int
    test_type_id: int
    template_id: Optional[int] = None
    status: str
    template_snapshot: Dict[str, Any]
    values: Dict[str, Any]
    flags: Dict[str, Any]
    notes: Optional[str] = None
    created_at: datetime
    updated_at: datetime


class PagedTestResultOut(APIModel):
    value: List[TestResultOut]
    Count: int


class ResultInstantiateFromSnapshot(APIModel):
    patient_id: int
    test_type_id: int
    # 🚀 THE CRITICAL ADDITION: Links to the original request for dates
    test_request_id: Optional[int] = None  
    
    template_id: Optional[int] = None
    template_snapshot: Dict[str, Any] = Field(default_factory=dict)
    values: Dict[str, Any] = Field(default_factory=dict)
    notes: Optional[str] = None
    sync_id: Optional[str] = Field(default=None, max_length=36)
    branch_id: Optional[int] = None 
    status: Optional[str] = None
