# seed.py
from app.db.init_db import init_db

if __name__ == "__main__":
    print("Zeroing and Re-seeding Database...")
    init_db()
    print("Success: Admin created (AdminI&E / Admin@2026)")