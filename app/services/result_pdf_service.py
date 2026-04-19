# -*- coding: utf-8 -*-
from pathlib import Path
from datetime import datetime

from app.services.portal_reports.builder import build_bundle_result
from app.services.portal_reports.renderer import render_pdf
from app.services.portal_reports.config import LAB_PROFILE

def generate_result_pdf(result, source="lab"):
    # ===============================
    # BUILD BUNDLE
    # ===============================
    payload = build_bundle_result(result)

    bundle_results = {
        str(result.id): payload
    }

    # ===============================
    # PATIENT DATA
    # ===============================
    patient = result.patient
    sex = patient.gender or "-"

    age = "-"
    if patient.date_of_birth:
        today = datetime.today()
        age = (
            today.year
            - patient.date_of_birth.year
            - ((today.month, today.day) < (patient.date_of_birth.month, patient.date_of_birth.day))
        )

    patient_row = {
        "Patient ID": patient.patient_no,
        "Name": patient.full_name,
        "Sex": sex,
        "Age": age,
        "Phone": patient.phone or "-"
    }

    # ===============================
    # OUTPUT PATH
    # ===============================
    output_dir = Path("generated_reports")
    output_dir.mkdir(exist_ok=True)

    output_path = output_dir / f"result_{result.id}.pdf"

    # ===============================
    # RENDER PDF
    # ===============================
    # 🔥 We now pass the 'source' through to the renderer
    render_pdf(
        output_path=output_path,
        lab_profile=LAB_PROFILE,
        patient_row=patient_row,
        bundle_results=bundle_results,
        source=source 
    )

    return output_path
