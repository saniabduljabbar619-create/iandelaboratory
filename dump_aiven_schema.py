import os
import pymysql

# Set once in your terminal before running:
#   $env:AIVEN_DB_PASSWORD = "<the real password>"
password = os.environ.get("AIVEN_DB_PASSWORD")
if not password:
    raise SystemExit("Set $env:AIVEN_DB_PASSWORD first - see comment above.")

conn = pymysql.connect(
    host="i-and-e-mysql-saniabduljabbar619-caa2.l.aivencloud.com",
    port=22695,
    user="avnadmin",
    password=password,
    database="defaultdb",
    ssl={"ssl": {}},
)
cur = conn.cursor()
cur.execute("SHOW TABLES")
tables = [r[0] for r in cur.fetchall()]

with open("aiven_schema_dump.sql", "w", encoding="utf-8") as f:
    f.write("SET FOREIGN_KEY_CHECKS=0;\n\n")
    for t in tables:
        cur.execute(f"SHOW CREATE TABLE `{t}`")
        row = cur.fetchone()
        f.write(row[1] + ";\n\n")
    f.write("SET FOREIGN_KEY_CHECKS=1;\n")

print(f"Wrote DDL for {len(tables)} tables to aiven_schema_dump.sql")
print("This file is SCHEMA ONLY - no patient data, no rows, just CREATE TABLE statements.")
conn.close()