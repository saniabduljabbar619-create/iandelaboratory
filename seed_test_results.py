# -*- coding: utf-8 -*-
# One-off: create a couple of approved results for testing the Result tab. Run once, delete.
from app.db.session import SessionLocal
from app.models.test_result import TestResult, ResultStatus
from app.models.patient import Patient
from app.models.test_type import TestType


def run():
    db = SessionLocal()
    try:
        # Test Portal Patient
        patient = db.query(Patient).filter(Patient.patient_no == "IEL-26-0002").first()
        if not patient:
            print("Patient IEL-26-0002 not found.")
            return

        fbc = db.query(TestType).filter(TestType.code == "FBC").first()
        widal = db.query(TestType).filter(TestType.code == "WIDAL").first()

        specs = [
            (fbc, {
                "fields": [
                    {"key": "Hb", "label": "Hemoglobin", "unit": "g/dL", "ref": {"low": 12, "high": 16}},
                    {"key": "WBC", "label": "White Blood Cells", "unit": "x10^9/L", "ref": {"low": 4, "high": 11}},
                ]
            }, {"Hb": 9.2, "WBC": 7.5}),
            (widal, {
                "fields": [
                    {"key": "TO", "label": "S. typhi O", "unit": "titre", "ref": {"low": 0, "high": 80}},
                    {"key": "TH", "label": "S. typhi H", "unit": "titre", "ref": {"low": 0, "high": 80}},
                ]
            }, {"TO": 160, "TH": 80}),
        ]

        created = 0
        for tt, snapshot, values in specs:
            if not tt:
                continue
            r = TestResult(
                patient_id=patient.id,
                test_type_id=tt.id,
                template_snapshot=snapshot,
                values=values,
                status=ResultStatus.approved,   # ready for release
                branch_id=patient.branch_id,
            )
            db.add(r)
            created += 1

        db.commit()
        print(f"✅ Created {created} approved results for {patient.full_name}. Result tab has data to release.")
    finally:
        db.close()


if __name__ == "__main__":
    run()