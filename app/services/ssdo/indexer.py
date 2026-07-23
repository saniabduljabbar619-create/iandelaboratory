# -*- coding: utf-8 -*-
# app/services/ssdo/indexer.py
"""
SSDO Indexer — writes SSDOIndex entries at record creation time.
Always called as a FastAPI BackgroundTask so it never blocks
the API response.
"""
from __future__ import annotations

from datetime import datetime
from typing import Optional

from sqlalchemy.orm import Session

from app.models.ssdo_index import SSDOIndex
from app.models.test_result import TestResult
from app.models.test_request import TestRequest
from app.models.patient import Patient
from app.services.ssdo.classifier import classify_record


class SSDOIndexer:

    def __init__(self, db: Session):
        self.db = db

    # --------------------------------------------------
    # CORE INDEXING
    # --------------------------------------------------

    def _upsert(self, record_type: str, record_id: int, data: dict) -> SSDOIndex:
        """Insert or update an SSDOIndex entry."""
        existing = (
            self.db.query(SSDOIndex)
            .filter(
                SSDOIndex.record_type == record_type,
                SSDOIndex.record_id == record_id,
            )
            .first()
        )

        if existing:
            for key, value in data.items():
                setattr(existing, key, value)
            existing.updated_at = datetime.utcnow()
            self.db.commit()
            return existing

        entry = SSDOIndex(record_type=record_type, record_id=record_id, **data)
        self.db.add(entry)
        self.db.commit()
        self.db.refresh(entry)
        return entry

    # --------------------------------------------------
    # INDEX A TEST RESULT
    # --------------------------------------------------

    def index_test_result(self, result_id: int) -> Optional[SSDOIndex]:
        """
        Classifies and indexes a TestResult.
        Called as BackgroundTask after result creation or update.
        """
        result: Optional[TestResult] = self.db.query(TestResult).filter(
            TestResult.id == result_id
        ).first()

        if not result:
            return None

        # Get test code from related test_type
        test_code = ""
        if result.test_type:
            test_code = result.test_type.code or ""

        classification = classify_record(
            test_code=test_code,
            values=result.values or {},
            flags=result.flags or {},
        )

        return self._upsert(
            record_type="test_result",
            record_id=result_id,
            data={
                "patient_id": result.patient_id,
                "test_category": classification["test_category"],
                "disease_tags": classification["disease_tags"],
                "severity_flag": classification["severity_flag"],
                "temporal_position": result.created_at,
                "portal_visible": result.status.value == "released"
                    if hasattr(result.status, "value") else False,
                "ai_processed": True,
                "ai_summary": {
                    "test_code": test_code,
                    "status": result.status.value
                        if hasattr(result.status, "value") else str(result.status),
                    "flag_count": len(result.flags or {}),
                    "classified_at": datetime.utcnow().isoformat(),
                },
                "branch_id": result.branch_id,
            },
        )

    # --------------------------------------------------
    # INDEX A TEST REQUEST
    # --------------------------------------------------

    def index_test_request(self, request_id: int) -> Optional[SSDOIndex]:
        """
        Indexes a TestRequest.
        Lighter classification — no values/flags at request stage.
        """
        request: Optional[TestRequest] = self.db.query(TestRequest).filter(
            TestRequest.id == request_id
        ).first()

        if not request:
            return None

        # Get test code
        from app.models.test_type import TestType
        test_type = self.db.query(TestType).filter(
            TestType.id == request.test_type_id
        ).first()
        test_code = test_type.code if test_type else ""

        from app.services.ssdo.classifier import classify_test_category
        category = classify_test_category(test_code)

        return self._upsert(
            record_type="test_request",
            record_id=request_id,
            data={
                "patient_id": request.patient_id,
                "test_category": category,
                "disease_tags": [],
                "severity_flag": "unknown",
                "temporal_position": request.created_at,
                "portal_visible": False,
                "ai_processed": True,
                "ai_summary": {
                    "test_code": test_code,
                    "status": request.status.value
                        if hasattr(request.status, "value") else str(request.status),
                    "classified_at": datetime.utcnow().isoformat(),
                },
                "branch_id": request.branch_id,
            },
        )

    # --------------------------------------------------
    # INDEX A PATIENT PROFILE
    # --------------------------------------------------

    def index_patient(self, patient_id: int) -> Optional[SSDOIndex]:
        """Indexes a patient profile record."""
        patient: Optional[Patient] = self.db.query(Patient).filter(
            Patient.id == patient_id
        ).first()

        if not patient:
            return None

        return self._upsert(
            record_type="patient_profile",
            record_id=patient_id,
            data={
                "patient_id": patient_id,
                "test_category": None,
                "disease_tags": [],
                "severity_flag": "unknown",
                "temporal_position": patient.created_at,
                "portal_visible": True,
                "ai_processed": True,
                "ai_summary": {
                    "full_name": patient.full_name,
                    "gender": patient.gender,
                    "classified_at": datetime.utcnow().isoformat(),
                },
                "branch_id": patient.branch_id,
            },
        )