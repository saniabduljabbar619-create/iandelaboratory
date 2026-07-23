import os
import sys
sys.path.insert(0, ".")

import sqlalchemy as sa
from app.db.base import Base
import app.models  # noqa: F401  registers all 33 tables

# Set once in your terminal before running:
#   $env:AIVEN_DB_PASSWORD = "<the real password>"
password = os.environ.get("AIVEN_DB_PASSWORD")
if not password:
    raise SystemExit("Set $env:AIVEN_DB_PASSWORD first - see comment above.")

AIVEN_URL = (
    f"mysql+pymysql://avnadmin:{password}"
    "@i-and-e-mysql-saniabduljabbar619-caa2.l.aivencloud.com:22695/defaultdb"
)

engine = sa.create_engine(AIVEN_URL, connect_args={"ssl": {"ssl": {}}})
insp = sa.inspect(engine)

db_tables = set(insp.get_table_names())
model_tables = set(Base.metadata.tables)

print(f"=== TABLE COMPARISON ===")
print(f"tables in Aiven   : {len(db_tables)}")
print(f"tables in models  : {len(model_tables)}")

missing_tables = sorted(model_tables - db_tables)
extra_tables = sorted(db_tables - model_tables)

print(f"\nMISSING from Aiven ({len(missing_tables)}):")
for t in missing_tables:
    print(f"  - {t}")

print(f"\nEXTRA in Aiven, not in models ({len(extra_tables)}):")
for t in extra_tables:
    print(f"  - {t}")

print(f"\n=== COLUMN-LEVEL CHECK (tables present on both sides) ===")
shared_tables = sorted(model_tables & db_tables)
any_column_diff = False

for table in shared_tables:
    db_cols = {c["name"] for c in insp.get_columns(table)}
    model_cols = set(Base.metadata.tables[table].columns.keys())

    missing_cols = model_cols - db_cols
    extra_cols = db_cols - model_cols

    if missing_cols or extra_cols:
        any_column_diff = True
        print(f"\n{table}:")
        if missing_cols:
            print(f"    model has, Aiven missing : {sorted(missing_cols)}")
        if extra_cols:
            print(f"    Aiven has, model missing : {sorted(extra_cols)}")

if not any_column_diff:
    print("no column differences on any shared table")

print(f"\n=== SUMMARY ===")
print(f"Missing tables : {len(missing_tables)}")
print(f"Extra tables   : {len(extra_tables)}")
print(f"Column diffs   : {'YES - see above' if any_column_diff else 'none'}")