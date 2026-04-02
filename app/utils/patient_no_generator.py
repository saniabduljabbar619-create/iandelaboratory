# -*- coding: utf-8 -*-
from sqlalchemy.orm import Session
from datetime import datetime
from app.models.patient import Patient

def generate_patient_no(db: Session) -> str:
    """
    Utility to generate the next Lab ID: IEL-YY-NNNN
    Aligned with PatientService for system-wide consistency.
    """
    # 1. Get current year suffix (e.g., '26')
    current_year_yy = datetime.now().strftime("%y") 
    prefix = "IEL"
    year_prefix = f"{prefix}-{current_year_yy}-"

    # 2. Find the highest number for the current year
    # We use .like() to ensure we stay within the current year's sequence
    last_patient = (
        db.query(Patient)
        .filter(Patient.patient_no.like(f"{year_prefix}%"))
        .order_by(Patient.patient_no.desc())
        .first()
    )

    if not last_patient:
        # Check if we are starting the 2026 sequence
        if current_year_yy == "26":
            nxt = 3150
        else:
            # Standard New Year reset for 2027 and beyond
            nxt = 1
    else:
        # 3. Parse the numeric tail (e.g., '3150' from 'IEL-26-3150')
        try:
            # We split by '-' and take the last part
            parts = last_patient.patient_no.split("-")
            nxt = int(parts[-1]) + 1
        except (ValueError, IndexError):
            nxt = 1

    # 4. Return formatted string (e.g., IEL-26-3151)
    return f"{year_prefix}{nxt:04d}"