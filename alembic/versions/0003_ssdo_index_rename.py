"""ssfo -> ssdo index rename + test_types.category index

Completes the SSFO -> SSDO rename at the database level: the ssdo_index
table's indexes were still named ix_ssfo_* from before the rename, even
though the model (app/models/ssdo_index.py) has declared ix_ssdo_* names
for a while. Purely cosmetic — same columns, same behavior, new names.

Also adds ix_test_types_category, which app/models/test_type.py has
declared (category = Column(..., index=True)) but was never migrated in.

Deliberately excludes three server-default removals that autogenerate
also detected (patients.portal_enabled, referrers.discount_percent,
test_requests.priority) — those are a real product decision, not a
mechanical cleanup, and are being tracked separately rather than folded
in here.

Revision ID: 0003_ssdo_index_rename
Revises: 0002_referrer_portal_credentials
Create Date: 2026-07-23
"""
from typing import Sequence, Union

from alembic import op

# revision identifiers, used by Alembic.
revision: str = "0003_ssdo_index_rename"
down_revision: Union[str, None] = "0002_referrer_portal_credentials"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


# (old_name, new_name, table, columns)
SSDO_INDEX_RENAMES = [
    ("ix_ssfo_category_severity", "ix_ssdo_category_severity", "ssdo_index", ["test_category", "severity_flag"]),
    ("ix_ssfo_index_ai_processed", "ix_ssdo_index_ai_processed", "ssdo_index", ["ai_processed"]),
    ("ix_ssfo_index_patient_id", "ix_ssdo_index_patient_id", "ssdo_index", ["patient_id"]),
    ("ix_ssfo_index_record_id", "ix_ssdo_index_record_id", "ssdo_index", ["record_id"]),
    ("ix_ssfo_index_record_type", "ix_ssdo_index_record_type", "ssdo_index", ["record_type"]),
    ("ix_ssfo_index_severity_flag", "ix_ssdo_index_severity_flag", "ssdo_index", ["severity_flag"]),
    ("ix_ssfo_index_temporal_position", "ix_ssdo_index_temporal_position", "ssdo_index", ["temporal_position"]),
    ("ix_ssfo_index_test_category", "ix_ssdo_index_test_category", "ssdo_index", ["test_category"]),
    ("ix_ssfo_patient_type", "ix_ssdo_patient_type", "ssdo_index", ["patient_id", "record_type"]),
]


def _index_names(table: str) -> set[str]:
    bind = op.get_bind()
    import sqlalchemy as sa
    inspector = sa.inspect(bind)
    return {ix["name"] for ix in inspector.get_indexes(table)}


def upgrade() -> None:
    existing = _index_names("ssdo_index")
    for old_name, new_name, table, cols in SSDO_INDEX_RENAMES:
        if new_name in existing:
            continue  # already renamed (e.g. re-run, or created fresh from an updated baseline)
        if old_name in existing:
            op.drop_index(old_name, table_name=table)
        op.create_index(new_name, table, cols, unique=False)

    test_types_existing = _index_names("test_types")
    if "ix_test_types_category" not in test_types_existing:
        op.create_index("ix_test_types_category", "test_types", ["category"], unique=False)


def downgrade() -> None:
    existing = _index_names("ssdo_index")
    if "ix_test_types_category" in _index_names("test_types"):
        op.drop_index("ix_test_types_category", table_name="test_types")

    for old_name, new_name, table, cols in reversed(SSDO_INDEX_RENAMES):
        if old_name in existing:
            continue
        if new_name in existing:
            op.drop_index(new_name, table_name=table)
        op.create_index(old_name, table, cols, unique=False)