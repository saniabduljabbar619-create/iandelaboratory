# -*- coding: utf-8 -*-
from __future__ import annotations

from pydantic import BaseModel, ConfigDict


class APIModel(BaseModel):
    """
    Base Pydantic model with ORM support (SQLAlchemy).
    """
    model_config = ConfigDict(from_attributes=True)
