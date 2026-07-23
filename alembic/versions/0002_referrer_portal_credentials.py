"""referrer portal credentials + reconcile out-of-band ALTERs

Adds the columns that were applied by hand via ALTER TABLE during development,
so that dev, prod (Aiven) and any fresh install all converge on the same schema.

Every operation here is guarded by a live inspection of the target database, so
this migration is safe to run against:
  * dev  — where portal_code / portal_code_expires_at already exist (no-op)
  * prod — where they do not (adds them)
  * a fresh DB built from 0001_baseline (adds them)

All changes are additive and nullable. No data is touched, no downtime needed.

Revision ID: 0002_referrer_portal_credentials
Revises: 0001_baseline
Create Date: 2026-07-23
"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision: str = "0002_referrer_portal_credentials"
down_revision: Union[str, None] = "0001_baseline"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


# (table, column, type) — additive, nullable, idempotent
ADDITIONS = [
    ("referrers", "portal_code", sa.String(length=255)),
    ("referrers", "portal_code_expires_at", sa.DateTime()),
    ("patients", "blood_group", sa.String(length=10)),
]


def _existing_columns(table: str) -> set[str]:
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    if table not in inspector.get_table_names():
        return set()
    return {c["name"] for c in inspector.get_columns(table)}


def upgrade() -> None:
    for table, column, type_ in ADDITIONS:
        if column not in _existing_columns(table):
            op.add_column(table, sa.Column(column, type_, nullable=True))


def downgrade() -> None:
    for table, column, _type in reversed(ADDITIONS):
        if column in _existing_columns(table):
            op.drop_column(table, column)