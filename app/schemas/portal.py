# -*- coding: utf-8 -*-
from __future__ import annotations

from datetime import datetime
from pydantic import Field
from app.schemas.common import APIModel


class PortalLogin(APIModel):
    phone: str
    patient_no: str


class PortalTokenOut(APIModel):
    token: str
    expires_at: datetime


class PortalResultItem(APIModel):
    id: int
    test_type_id: int
    template_id: int
    status: str
    created_at: datetime
