# -*- coding: utf-8 -*-
from __future__ import annotations

from sqlalchemy.orm import Session
from app.models.audit_log import AuditLog


class AuditService:
    def __init__(self, db: Session):
        self.db = db

    def log(self, **kwargs) -> None:
        row = AuditLog(**kwargs)
        self.db.add(row)
        self.db.commit()
