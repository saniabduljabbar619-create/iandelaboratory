# app/services/portal_reports/config.py
from pathlib import Path


CURRENT_FILE = Path(__file__).resolve()
APP_ROOT = CURRENT_FILE.parents[2] 

LAB_PROFILE = {
    "lab_name": "I and E Diagnostic Laboratory and Ultra Sound Scan",
    "address": "NO : 001 Na'ibawa, Kano - Zaria Road, Tarauni, Kano, Nigeria",
    "phone": "08063645308 |",
    "email": "iandelaboratory@yahoo.com",

    # Correct path
    "logo_path": str(APP_ROOT / "static" / "logos" / "logo.png"),

    "watermark_enabled": True,

    "scientist_name": "",
    "scientist_qualification": "",

    "report_notes": (
        "Online downloadable results are for personal reference only. "
        "Visit the laboratory for official authentication."
    )
}
