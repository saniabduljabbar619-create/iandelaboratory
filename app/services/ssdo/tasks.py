# -*- coding: utf-8 -*-
# app/services/ssdo/tasks.py
"""
Background-safe SSDO task wrappers.
Each function opens its own DB session — never reuses a
request-scoped session, since background tasks may run after
the request's session has already closed.
"""
from __future__ import annotations

from app.db.session import SessionLocal
from app.services.ssdo.indexer import SSDOIndexer


def index_result_task(result_id: int) -> None:
    db = SessionLocal()
    try:
        SSDOIndexer(db).index_test_result(result_id)
    except Exception as exc:
        print(f"[SSDO] Failed to index result {result_id}: {exc}")
    finally:
        db.close()


def index_request_task(request_id: int) -> None:
    db = SessionLocal()
    try:
        SSDOIndexer(db).index_test_request(request_id)
    except Exception as exc:
        print(f"[SSDO] Failed to index request {request_id}: {exc}")
    finally:
        db.close()


def index_patient_task(patient_id: int) -> None:
    db = SessionLocal()
    try:
        SSDOIndexer(db).index_patient(patient_id)
    except Exception as exc:
        print(f"[SSDO] Failed to index patient {patient_id}: {exc}")
    finally:
        db.close()