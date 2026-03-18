from sqlalchemy.orm import Session
from sqlalchemy import func
from app.models.patient import Patient


def generate_patient_no(db: Session) -> str:

    last_patient = (
        db.query(Patient)
        .order_by(Patient.id.desc())
        .first()
    )

    if not last_patient:
        return "LPT-0001"

    last_no = last_patient.patient_no

    try:
        number = int(last_no.split("-")[1])
    except:
        number = 0

    next_number = number + 1

    return f"LPT-{next_number:04d}"