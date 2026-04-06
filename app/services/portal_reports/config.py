from pathlib import Path

CURRENT_FILE = Path(__file__).resolve()
APP_ROOT = CURRENT_FILE.parents[2]

# ✅ define path first
logo_path = APP_ROOT / "web" / "static" / "logos" / "logo.png"

# ✅ debug prints
print("LOGO PATH:", logo_path)
print("LOGO EXISTS:", logo_path.exists())

LAB_PROFILE = {
    "lab_name": "I and E Diagnostic Laboratory and Ultrasound Scan",
    "address": "NO : 514 Yar Akwa, Zaria Road, Opp First Bank, Kano State, Nigeria",
    "phone": "08063645308 |",
    "email": "iandelaboratory@yahoo.com",

    # ✅ correct usage
    "logo_path": str(logo_path) if logo_path.exists() else None,

    "watermark_enabled": True,

    "scientist_name": "",
    "scientist_qualification": "",

    "report_notes": (
        "Online downloadable results are for personal reference only. "
        "Visit the laboratory for official authentication."
    )
}
