# -*- coding: utf-8 -*-
from __future__ import annotations

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from app.core.config import settings

engine = create_engine(
    settings.DATABASE_URL,
    pool_pre_ping=True,
    connect_args={"ssl": {"ssl_disabled": False}},
)

SessionLocal = sessionmaker(bind=engine, autocommit=False, autoflush=False)








