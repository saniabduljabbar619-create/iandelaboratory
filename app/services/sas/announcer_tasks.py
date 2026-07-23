# -*- coding: utf-8 -*-
# app/services/sas/announcer_tasks.py
"""
Background-safe announcer task wrappers.
Called as FastAPI BackgroundTasks — each opens its own DB session.
Integrated into the result and request creation flow automatically.
"""
from __future__ import annotations

from app.db.session import SessionLocal
from app.services.sas.announcer import AnnouncerService
from app.models.ssdo_index import SSDOIndex


def announce_new_request_task(request_id: int, branch_id: int = None) -> None:
    db = SessionLocal()
    try:
        AnnouncerService(db, branch_id=branch_id).announce_new_request(request_id)
    except Exception as exc:
        print(f"[SAS Announcer] Failed to announce request {request_id}: {exc}")
    finally:
        db.close()


def announce_result_by_severity_task(result_id: int, branch_id: int = None) -> None:
    """
    Checks SSDO severity for a result and fires the correct announcement.
    Called automatically after SSDO indexing completes.
    """
    db = SessionLocal()
    try:
        entry = db.query(SSDOIndex).filter(
            SSDOIndex.record_type == "test_result",
            SSDOIndex.record_id == result_id,
        ).first()

        if not entry:
            return

        svc = AnnouncerService(db, branch_id=branch_id)

        if entry.severity_flag == "critical":
            svc.announce_critical_result(result_id)
        elif entry.severity_flag == "abnormal":
            svc.announce_abnormal_result(
                result_id,
                entry.disease_tags or []
            )
        # normal results are silent — no announcement needed
    except Exception as exc:
        print(f"[SAS Announcer] Failed to announce result {result_id}: {exc}")
    finally:
        db.close()