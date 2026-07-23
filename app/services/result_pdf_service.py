# -*- coding: utf-8 -*-
# app/services/result_pdf_service.py
from pathlib import Path
from datetime import datetime

from app.services.portal_reports.builder import build_bundle_result
from app.services.portal_reports.renderer import render_pdf
from app.services.portal_reports.config import LAB_PROFILE


def generate_result_pdf(result, source="lab", requested_at=None):

    # ── Build payload ──
    payload = build_bundle_result(result)
    bundle_results = {str(result.id): payload}

    # ── Patient data ──
    patient = result.patient
    sex = patient.gender or "-"
    age = "-"
    if getattr(patient, "age_value", None):
        age = f"{patient.age_value} {patient.age_unit or ''}".strip()
    elif patient.date_of_birth:
        today = datetime.today()
        age = (
            today.year
            - patient.date_of_birth.year
            - ((today.month, today.day) < (patient.date_of_birth.month, patient.date_of_birth.day))
        )

    # ── Accountability metadata chain ──
    lab_number = "-"
    request_time = "-"
    try:
        from app.models.test_request import TestRequest
        from sqlalchemy import inspect as _sa_inspect
        session = _sa_inspect(result).session
        if session is not None:
            req = (
                session.query(TestRequest)
                .filter(TestRequest.test_result_id == result.id)
                .first()
            )
            if req is not None:
                lab_number = req.lab_number or "-"
                if req.created_at:
                    request_time = req.created_at.strftime("%d %b %Y, %I:%M %p")
    except Exception:
        pass

    report_time = "-"
    if result.created_at:
        report_time = result.created_at.strftime("%d %b %Y, %I:%M %p")

    release_time = "-"
    status_val = result.status.value if hasattr(result.status, "value") else str(result.status)
    released_at = getattr(result, "released_at", None) or getattr(result, "updated_at", None)
    if status_val == "released" and released_at:
        release_time = released_at.strftime("%d %b %Y, %I:%M %p")

    patient_row = {
        "Patient ID": patient.patient_no,
        "Name": patient.full_name,
        "Sex": sex,
        "Age": age,
        "Phone": patient.phone or "-",
        "Lab Number": lab_number,
        "Requested": request_time,
        "Reported": report_time,
        "Released": release_time,
    }

    report_number = f"SLX-{result.id:05d}"
    sas_assisted = bool(result.sas_predictions)

    output_dir = Path("generated_reports")
    output_dir.mkdir(exist_ok=True)
    output_path = output_dir / f"result_{result.id}.pdf"

    render_pdf(
        output_path=output_path,
        lab_profile=LAB_PROFILE,
        patient_row=patient_row,
        bundle_results=bundle_results,
        source=source,
        requested_at=result.created_at,
        result_sync_id=result.sync_id,
        report_number=report_number,
        sas_assisted=sas_assisted,
    )

    return output_path


def generate_bundle_pdf(results, source="lab"):
    """
    Render MULTIPLE results for the SAME patient into one combined report.
    Shares one header/patient block; each result's tables stack under it.
    """
    if not results:
        raise ValueError("No results provided for bundle.")

    from app.services.portal_reports.builder import build_bundle_result

    patient = results[0].patient
    sex = patient.gender or "-"
    age = "-"
    if getattr(patient, "age_value", None):
        age = f"{patient.age_value} {patient.age_unit or ''}".strip()
    elif patient.date_of_birth:
        today = datetime.today()
        age = (
            today.year - patient.date_of_birth.year
            - ((today.month, today.day) < (patient.date_of_birth.month, patient.date_of_birth.day))
        )

    lab_number = "-"
    request_time = "-"
    try:
        from app.models.test_request import TestRequest
        from sqlalchemy import inspect as _sa_inspect
        session = _sa_inspect(results[0]).session
        if session is not None:
            rids = [r.id for r in results]
            reqs = session.query(TestRequest).filter(TestRequest.test_result_id.in_(rids)).all()
            if reqs:
                reqs_sorted = sorted([r for r in reqs if r.created_at], key=lambda x: x.created_at)
                if reqs_sorted:
                    request_time = reqs_sorted[0].created_at.strftime("%d %b %Y, %I:%M %p")
                for rq in reqs:
                    if rq.lab_number:
                        lab_number = rq.lab_number
                        break
    except Exception:
        pass

    report_time = "-"
    created_times = [r.created_at for r in results if r.created_at]
    if created_times:
        report_time = min(created_times).strftime("%d %b %Y, %I:%M %p")

    release_time = "-"
    rel_times = []
    for r in results:
        status_val = r.status.value if hasattr(r.status, "value") else str(r.status)
        rt = getattr(r, "released_at", None) or getattr(r, "updated_at", None)
        if status_val == "released" and rt:
            rel_times.append(rt)
    if rel_times:
        release_time = max(rel_times).strftime("%d %b %Y, %I:%M %p")

    patient_row = {
        "Patient ID": patient.patient_no,
        "Name": patient.full_name,
        "Sex": sex,
        "Age": age,
        "Phone": patient.phone or "-",
        "Lab Number": lab_number,
        "Requested": request_time,
        "Reported": report_time,
        "Released": release_time,
    }

    bundle_results = {}
    sas_assisted = False
    for r in results:
        bundle_results[str(r.id)] = build_bundle_result(r)
        if r.sas_predictions:
            sas_assisted = True

    result_sync_id = results[0].sync_id

    output_dir = Path("generated_reports")
    output_dir.mkdir(exist_ok=True)
    ids_tag = "_".join(str(r.id) for r in results[:4])
    output_path = output_dir / f"bundle_{ids_tag}.pdf"

    render_pdf(
        output_path=output_path,
        lab_profile=LAB_PROFILE,
        patient_row=patient_row,
        bundle_results=bundle_results,
        source=source,
        requested_at=min(created_times) if created_times else None,
        result_sync_id=result_sync_id,
        report_number=None,
        sas_assisted=sas_assisted,
    )
    return output_path