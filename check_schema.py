# -*- coding: utf-8 -*-
"""Pre-stamp check: does the live DB match the models? Read-only."""
import sqlalchemy as sa

from app.core.config import settings
from app.db.base import Base
import app.models  # noqa: F401  registers all 33 tables

engine = sa.create_engine(settings.DATABASE_URL)
insp = sa.inspect(engine)

db_tables = set(insp.get_table_names()) - {"alembic_version"}
model_tables = set(Base.metadata.tables)

print(f"tables in database : {len(db_tables)}")
print(f"tables in models   : {len(model_tables)}")

missing = model_tables - db_tables
extra = db_tables - model_tables

print(f"\nmissing from DB    : {sorted(missing) or 'none'}")
print(f"extra in DB        : {sorted(extra) or 'none'}")

print("\n--- columns 0002 will handle ---")
for table, col in [
    ("referrers", "portal_code"),
    ("referrers", "portal_code_expires_at"),
    ("patients", "blood_group"),
]:
    if table in db_tables:
        cols = {c["name"] for c in insp.get_columns(table)}
        print(f"{table}.{col:<24} {'present' if col in cols else 'MISSING -> will be added'}")
    else:
        print(f"{table}.{col:<24} table not found!")

print("\nOK to stamp" if not missing else "\nDO NOT STAMP - tables missing, tell Claude")