# app/services/portal_reports/config.py
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parents[3]

LAB_PROFILE = {
    "lab_name": "I and E Diagnostic Laboratory and Ultra Sound Scan",
    "address": "NO : 001 Na'ibawa, Kano - Zaria Road, Tarauni, Kano, Nigeria",
    "phone": "08063645308 |",
    "email": "iandelaboratory@yahoo.com",

    # Correct path
    "logo_path": str(BASE_DIR / "static" / "logos" / "logo.jpeg"),

    "watermark_enabled": True,

    "scientist_name": "",
    "scientist_qualification": "",

    "report_notes": (
        "Online downloadable results are for personal reference only. "
        "Visit the laboratory for official authentication."
    )
}