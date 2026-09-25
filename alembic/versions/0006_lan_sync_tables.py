"""LAN <-> cloud sync bookkeeping tables: sync_outbox, sync_map, sync_state

New tables only; no existing table is touched. Guarded by live inspection,
so it is a no-op wherever app startup (init_db's create_all) already
created them.

Revision ID: 0006_lan_sync_tables
Revises: 0005_v2_legacy_catchup
Create Date: 2026-09-25
"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import mysql

# revision identifiers, used by Alembic.
revision: str = "0006_lan_sync_tables"
down_revision: Union[str, None] = "0005_v2_legacy_catchup"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

PRECISE_DATETIME = sa.DateTime().with_variant(mysql.DATETIME(fsp=6), "mysql")


def upgrade() -> None:
    existing = set(sa.inspect(op.get_bind()).get_table_names())

    if "sync_outbox" not in existing:
        op.create_table(
            "sync_outbox",
            sa.Column("id", sa.BigInteger(), primary_key=True, autoincrement=True),
            sa.Column("table_name", sa.String(length=64), nullable=False),
            sa.Column("row_id", sa.BigInteger(), nullable=False),
            sa.Column("sync_id", sa.String(length=100), nullable=False),
            sa.Column("op", sa.String(length=10), nullable=False),
            sa.Column("changed_at", PRECISE_DATETIME, nullable=False),
        )
        op.create_index("ix_sync_outbox_row", "sync_outbox", ["table_name", "row_id"])

    if "sync_map" not in existing:
        op.create_table(
            "sync_map",
            sa.Column("id", sa.BigInteger(), primary_key=True, autoincrement=True),
            sa.Column("table_name", sa.String(length=64), nullable=False),
            sa.Column("local_id", sa.BigInteger(), nullable=False),
            sa.Column("sync_id", sa.String(length=100), nullable=False, unique=True),
        )
        op.create_index("ix_sync_map_local", "sync_map", ["table_name", "local_id"])

    if "sync_state" not in existing:
        op.create_table(
            "sync_state",
            sa.Column("key", sa.String(length=100), primary_key=True),
            sa.Column("value", sa.Text(), nullable=True),
            sa.Column("updated_at", sa.DateTime(), server_default=sa.func.now(), nullable=True),
        )


def downgrade() -> None:
    op.drop_table("sync_state")
    op.drop_table("sync_map")
    op.drop_table("sync_outbox")
