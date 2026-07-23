"""v2.0 legacy database catch-up: create missing tables + columns

For any database that has never run through 0001-0004 (i.e. one that was
built by an older deployed version of the app, before this session's v2.0
work existed) — this brings it fully up to the current model state in one
deliberate, guarded step.

Context: Aiven (production) was discovered to be missing all 12 "v2.0 —
new models" tables (subscriptions, ssdo_index, blood bank, analytics,
voice_announcements, portal_auth_attempts) plus v2.0 columns on 5 existing
tables (patients, referrers, test_requests, test_results, test_types).
This happened because production has been running pre-v2.0 code this whole
time; nothing was ever lost or broken — the tables/columns simply never
existed there yet.

Every operation here is guarded by a live inspection of the target
database, so this migration is safe to run against:
  * dev / any DB already at 0004  — complete no-op, everything exists
  * Aiven (or any similarly legacy DB) — creates exactly what's missing
  * a fresh DB built from 0001_baseline alone — no-op, 0001 already
    created everything this migration would otherwise add

Never touches existing tables' data, never drops or renames anything.

Revision ID: 0005_v2_legacy_catchup
Revises: 0004_formalize_server_defaults
Create Date: 2026-07-23
"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision: str = "0005_v2_legacy_catchup"
down_revision: Union[str, None] = "0004_formalize_server_defaults"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


# Every column this migration might add, across the 5 tables that can be
# partially behind. (table, column, type, server_default_or_None, nullable)
COLUMN_ADDITIONS = [
    # patients
    ("patients", "age_value", sa.Integer(), None, True),
    ("patients", "age_unit", sa.String(length=10), None, True),
    ("patients", "blood_group", sa.String(length=10), None, True),
    ("patients", "email", sa.String(length=255), None, True),
    ("patients", "portal_code", sa.String(length=255), None, True),
    ("patients", "portal_enabled", sa.Boolean(), "1", False),
    ("patients", "referrer_id", sa.Integer(), None, True),
    # referrers
    ("referrers", "avatar_path", sa.String(length=500), None, True),
    ("referrers", "portal_code", sa.String(length=255), None, True),
    ("referrers", "portal_code_expires_at", sa.DateTime(), None, True),
    ("referrers", "organization_type", sa.String(length=50), None, True),
    ("referrers", "address", sa.String(length=500), None, True),
    ("referrers", "contact_person", sa.String(length=255), None, True),
    ("referrers", "license_no", sa.String(length=100), None, True),
    ("referrers", "discount_percent", sa.Numeric(precision=5, scale=2), "0.00", False),
    ("referrers", "notes", sa.Text(), None, True),
    ("referrers", "updated_at", sa.DateTime(), None, True),
    # test_requests
    ("test_requests", "lab_number", sa.String(length=50), None, True),
    ("test_requests", "priority", sa.String(length=20), "normal", False),
    # test_results  (v2.0 SAS prediction storage — lab_no left untouched deliberately,
    # it's a legacy field not in the current model; out of scope, not dropped)
    ("test_results", "sas_predictions", sa.JSON(), None, True),
    ("test_results", "sas_confidence", sa.JSON(), None, True),
    ("test_results", "sas_accepted", sa.JSON(), None, True),
    # test_types
    ("test_types", "category", sa.String(length=50), None, True),
]

# The 12 tables that may not exist yet at all.
NEW_TABLE_NAMES = [
    "system_config",
    "subscription_tiers",
    "subscriptions",
    "trial_records",
    "ssdo_index",
    "blood_donors",
    "blood_inventory",
    "cross_matches",
    "analytics_snapshots",
    "disease_weekly_trends",
    "voice_announcements",
    "portal_auth_attempts",
]

# test_types.category needs its index too (mirrors 0003 for any DB skipping straight here)
EXTRA_INDEXES = [
    ("test_types", "ix_test_types_category", ["category"]),
]


def _existing_tables() -> set[str]:
    bind = op.get_bind()
    return set(sa.inspect(bind).get_table_names())


def _existing_columns(table: str) -> set[str]:
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    if table not in inspector.get_table_names():
        return set()
    return {c["name"] for c in inspector.get_columns(table)}


def _existing_indexes(table: str) -> set[str]:
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    if table not in inspector.get_table_names():
        return set()
    return {ix["name"] for ix in inspector.get_indexes(table)}


def upgrade() -> None:
    # 1. Create any of the 12 tables that don't exist yet, using the CURRENT
    #    model definitions (imported lazily so this migration has no import-time
    #    dependency beyond what alembic/env.py already sets up).
    from app.db.base import Base
    import app.models  # noqa: F401  registers all 33 tables

    existing = _existing_tables()
    missing_table_names = [t for t in NEW_TABLE_NAMES if t not in existing]

    if missing_table_names:
        bind = op.get_bind()
        tables_to_create = [Base.metadata.tables[name] for name in missing_table_names]
        Base.metadata.create_all(bind=bind, tables=tables_to_create)

    # 2. Add any missing columns on the 5 tables that may be partially behind.
    for table, column, type_, default, nullable in COLUMN_ADDITIONS:
        if column not in _existing_columns(table):
            op.add_column(table, sa.Column(column, type_, server_default=default, nullable=nullable))

    # 3. Add any missing indexes not already covered by table creation above.
    for table, index_name, cols in EXTRA_INDEXES:
        if index_name not in _existing_indexes(table):
            op.create_index(index_name, table, cols, unique=False)


def downgrade() -> None:
    # Deliberately not implemented: this migration exists to bring a legacy
    # database up to current state. Reversing it would mean dropping tables
    # and columns that may by then hold real data (referrer portal codes,
    # blood bank records, SAS predictions, etc.) — too destructive to do
    # unconditionally. Restore from the pre-migration backup instead.
    raise NotImplementedError(
        "0005 is not reversible via downgrade — restore from backup taken "
        "before this migration was applied."
    )