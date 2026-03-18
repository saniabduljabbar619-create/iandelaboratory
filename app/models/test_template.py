# -*- coding: utf-8 -*-
from __future__ import annotations

from sqlalchemy import Column, Integer, String, DateTime, func, ForeignKey, JSON, Boolean, Index
from sqlalchemy.orm import relationship
from app.db.base import Base


class TestTemplate(Base):
    """
    Canonical template that defines how a result looks and how it is computed.
    This enables 'no recreation' rule: users never retype template structure.
    """
    __tablename__ = "test_templates"

    id = Column(Integer, primary_key=True)

    test_type_id = Column(Integer, ForeignKey("test_types.id"), nullable=False, index=True)
    title = Column(String(255), nullable=False, index=True)

    # structure = fields, units, reference ranges, table layout, etc.
    # rules = calculations / derived fields
    structure = Column(JSON, nullable=False)
    rules = Column(JSON, nullable=True)

    is_active = Column(Boolean, default=True, nullable=False)

    created_at = Column(DateTime, server_default=func.now(), nullable=False)
    updated_at = Column(DateTime, server_default=func.now(), onupdate=func.now(), nullable=False)

    test_type = relationship("TestType", lazy="joined")


Index("ix_templates_test_type_active", TestTemplate.test_type_id, TestTemplate.is_active)
