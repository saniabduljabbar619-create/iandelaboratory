# -*- coding: utf-8 -*-
# alembic/env.py — Solunex Lab Backend
from __future__ import annotations

import os
import sys
from logging.config import fileConfig
from pathlib import Path

from sqlalchemy import engine_from_config, pool
from alembic import context

# --- make the app importable when alembic runs from the project root ---
ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from app.db.base import Base          # noqa: E402
import app.models                     # noqa: F401,E402  <-- registers ALL 33 tables

config = context.config

if config.config_file_name is not None:
    fileConfig(config.config_file_name)

target_metadata = Base.metadata


def get_url() -> str:
    """
    Resolution order:
      1. `alembic -x db_url=...`      (one-off, e.g. pointing at Aiven prod)
      2. ALEMBIC_DATABASE_URL env var
      3. settings.DATABASE_URL        (normal dev path, reads .env)
    """
    x_args = context.get_x_argument(as_dictionary=True)
    if x_args.get("db_url"):
        return x_args["db_url"]

    env_url = os.getenv("ALEMBIC_DATABASE_URL")
    if env_url:
        return env_url

    from app.core.config import settings
    return settings.DATABASE_URL


def run_migrations_offline() -> None:
    context.configure(
        url=get_url(),
        target_metadata=target_metadata,
        literal_binds=True,
        dialect_opts={"paramstyle": "named"},
        compare_type=True,
        compare_server_default=True,
    )
    with context.begin_transaction():
        context.run_migrations()


def run_migrations_online() -> None:
    section = config.get_section(config.config_ini_section) or {}
    section["sqlalchemy.url"] = get_url()

    connectable = engine_from_config(
        section,
        prefix="sqlalchemy.",
        poolclass=pool.NullPool,
    )

    with connectable.connect() as connection:
        context.configure(
            connection=connection,
            target_metadata=target_metadata,
            compare_type=True,
            compare_server_default=True,
        )
        with context.begin_transaction():
            context.run_migrations()


if context.is_offline_mode():
    run_migrations_offline()
else:
    run_migrations_online()