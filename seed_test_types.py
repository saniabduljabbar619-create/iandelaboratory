# -*- coding: utf-8 -*-
# One-off: seed a realistic Nigerian lab test catalog. Run once, then delete.
from app.db.session import SessionLocal
from app.models.test_type import TestType

CATALOG = [
    # Haematology
    ("FBC", "Full Blood Count", "Haematology", 4000),
    ("ESR", "Erythrocyte Sedimentation Rate", "Haematology", 2000),
    ("PCV", "Packed Cell Volume", "Haematology", 1500),
    ("GENOTYPE", "Genotype", "Haematology", 2500),
    ("BLOOD_GROUP", "Blood Group", "Haematology", 2000),
    ("SICKLING", "Sickling Test", "Haematology", 2000),
    ("PT_INR", "Prothrombin Time / INR", "Haematology", 5000),
    # Biochemistry
    ("LFT", "Liver Function Test", "Biochemistry", 8000),
    ("RFT", "Renal Function Test", "Biochemistry", 8000),
    ("FBS", "Fasting Blood Sugar", "Biochemistry", 2000),
    ("RBS", "Random Blood Sugar", "Biochemistry", 2000),
    ("HBA1C", "Glycated Haemoglobin (HbA1c)", "Biochemistry", 7000),
    ("LIPID", "Lipid Profile", "Biochemistry", 9000),
    ("URIC_ACID", "Uric Acid", "Biochemistry", 3500),
    ("ELECTROLYTES", "Serum Electrolytes", "Biochemistry", 7000),
    # Microbiology
    ("URINE_MCS", "Urine Microscopy, Culture & Sensitivity", "Microbiology", 6000),
    ("WIDAL", "Widal Test", "Microbiology", 3000),
    ("STOOL_MCS", "Stool Microscopy & Culture", "Microbiology", 5000),
    ("HVS", "High Vaginal Swab MCS", "Microbiology", 6000),
    ("AFB", "Sputum AFB (TB)", "Microbiology", 4000),
    # Parasitology
    ("MP", "Malaria Parasite", "Parasitology", 2000),
    ("BF_MP", "Blood Film for MP", "Parasitology", 2500),
    # Serology
    ("HBSAG", "Hepatitis B Surface Antigen", "Serology", 3000),
    ("HCV", "Hepatitis C Antibody", "Serology", 3500),
    ("HIV", "HIV Screening", "Serology", 2500),
    ("VDRL", "VDRL (Syphilis)", "Serology", 2500),
    ("PREGNANCY", "Pregnancy Test (hCG)", "Serology", 1500),
    ("PSA", "Prostate Specific Antigen", "Serology", 8000),
    ("H_PYLORI", "H. Pylori Antibody", "Serology", 4000),
]


def run():
    db = SessionLocal()
    try:
        created = 0
        for code, name, category, price in CATALOG:
            exists = db.query(TestType).filter(TestType.code == code).first()
            if exists:
                if not exists.category:
                    exists.category = category
                continue
            db.add(TestType(code=code, name=name, category=category, price=price, is_active=True))
            created += 1
        db.commit()
        print(f"✅ Seeded {created} new test types. Catalog ready.")
    finally:
        db.close()


if __name__ == "__main__":
    run()