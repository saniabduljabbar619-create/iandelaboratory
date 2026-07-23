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
cur.execute("SHOW COLUMNS FROM referrers LIKE 'portal_code'")
row = cur.fetchone()
print("portal_code exists:", row is not None)

cur.execute("SHOW COLUMNS FROM referrers LIKE 'portal_code_expires_at'")
row2 = cur.fetchone()
print("portal_code_expires_at exists:", row2 is not None)

cur.execute("SHOW TABLES")
tables = [r[0] for r in cur.fetchall()]
print("total tables:", len(tables))
conn.close()