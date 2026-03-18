# -*- coding: utf-8 -*-
from __future__ import annotations

from enum import Enum


class UserRole(str, Enum):
    admin = "admin"
    reception = "reception"
    labtech = "labtech"
    supervisor = "supervisor"


class ResultStatus(str, Enum):
    draft = "draft"
    in_progress = "in_progress"
    pending_review = "pending_review"
    approved = "approved"
    released = "released"
