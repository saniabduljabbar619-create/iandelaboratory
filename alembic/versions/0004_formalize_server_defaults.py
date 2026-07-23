"""formalize server-side defaults: priority, discount_percent, portal_enabled

These three columns already had a server-level default on dev and prod
(added by hand at some point, outside of any migration), but the Python
models only ever declared a client-side `default=`. 0001_baseline was
generated from the models, so it built these columns WITHOUT a
server_default — meaning a fresh database built purely from migrations
would silently differ from the existing dev/prod databases.

Decision (2026-07-23): keep the server-side defaults. This migration
formalizes that decision by adding them at the DB level, and the models
(app/models/test_request.py, referrer.py, patient.py) have been updated
to declare server_default= to match, so this stops showing up as drift
on every future `alembic revision --autogenerate`.

Guarded by inspection, so this is a genuine no-op on any database where
the default is already present (dev, prod) — it only does real work on a
database built fresh from 0001_baseline alone.

Revision ID: 0004_formalize_server_defaults
Revises: 0003_ssdo_index_rename
Create Date: 2026-07-23
"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision: str = "0004_formalize_server_defaults"
down_revision: Union[str, None] = "0003_ssdo_index_rename"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


# (table, column, sqlalchemy type, server_default literal)
DEFAULTS = [
    ("test_requests", "priority", sa.String(length=20), "normal"),
    ("referrers", "discount_percent", sa.Numeric(precision=5, scale=2), "0.00"),
    ("patients", "portal_enabled", sa.Boolean(), "1"),
]


def _has_server_default(table: str, column: str) -> bool:
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    for col in inspector.get_columns(table):
        if col["name"] == column:
            return col.get("default") is not None
    return False


def upgrade() -> None:
    for table, column, type_, default in DEFAULTS:
        if not _has_server_default(table, column):
            op.alter_column(table, column, existing_type=type_, server_default=default)


def downgrade() -> None:
    # Reverts to the pre-formalization state: client-side default only,
    # no server-side default. Matches what 0001_baseline originally built.
    for table, column, type_, _default in reversed(DEFAULTS):
        if _has_server_default(table, column):
            op.alter_column(table, column, existing_type=type_, server_default=None)