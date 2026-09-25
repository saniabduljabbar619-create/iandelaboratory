# -*- coding: utf-8 -*-
from __future__ import annotations

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from app.core.config import settings

connect_args = {}
if settings.DB_SSL and settings.DATABASE_URL.startswith("mysql"):
    connect_args = {"ssl": {"ssl_disabled": False}}

engine = create_engine(
    settings.DATABASE_URL,
    pool_pre_ping=True,
    connect_args=connect_args,
)

SessionLocal = sessionmaker(bind=engine, autocommit=False, autoflush=False)
