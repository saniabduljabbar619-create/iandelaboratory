# -*- coding: utf-8 -*-
from __future__ import annotations

from datetime import datetime
from typing import Optional, Any, Dict

from app.schemas.common import APIModel


class AuditLogOut(APIModel):
    id: int
    actor_type: str
    actor: Optional[str] = None
    action: str
    entity: Optional[str] = None
    entity_id: Optional[int] = None
    ip: Optional[str] = None
    meta: Optional[Dict[str, Any]] = None
    created_at: datetime
