# -*- coding: utf-8 -*-
# app/services/portal_service.py — LabCore v2.0
from __future__ import annotations

import hmac
import hashlib
import base64
import json
from datetime import datetime, timedelta, timezone
from typing import Optional

from fastapi import HTTPException
from sqlalchemy.orm import Session

from app.models.patient import Patient
from app.models.test_result import TestResult, ResultStatus
from app.models.portal_auth import PortalAuthAttempt
from app.core.config import settings


class PortalService:
    """
    Portal authentication service.
    - Login: phone + patient_no
    - Token: HMAC-signed payload {patient_id, exp, kind: "portal"}
    - Brute-force protection: PORTAL_MAX_FAILS attempts → PORTAL_LOCK_MINUTES lockout
    """

    def __init__(self, db: Session, secret: str):
        self.db = db
        self.secret = secret.encode("utf-8")
        self.max_fails = settings.PORTAL_MAX_FAILS
        self.lock_minutes = settings.PORTAL_LOCK_MINUTES

    # --------------------------------------------------
    # AUTH
    # --------------------------------------------------

    def login(self, phone: str, patient_no: str, ip: Optional[str] = None) -> dict:
        # Check brute-force lockout first
        self._check_lockout(phone, ip)

        patient = (
            self.db.query(Patient)
            .filter(Patient.phone == phone, Patient.patient_no == patient_no)
            .first()
        )

        if not patient:
            self._record_failed_attempt(phone, ip)
            raise HTTPException(
                status_code=401,
                detail="Invalid phone number or patient ID."
            )

        # Success — reset attempt counter
        self._reset_attempts(phone)

        token_exp = settings.PORTAL_JWT_EXPIRES_MIN
        exp = datetime.now(timezone.utc) + timedelta(minutes=token_exp)
        payload = {
            "patient_id": patient.id,
            "patient_no": patient.patient_no,
            "kind": "portal",
            "exp": int(exp.timestamp()),
        }

        return {
            "token": self._sign(payload),
            "expires_at": exp,
            "patient_id": patient.id,
            "patient_name": patient.full_name,
        }

    def verify_token(self, token: str) -> int:
        payload = self._verify(token)
        if payload.get("kind") != "portal":
            raise HTTPException(status_code=401, detail="Invalid portal token.")
        if payload["exp"] < int(datetime.now(timezone.utc).timestamp()):
            raise HTTPException(status_code=401, detail="Portal token expired.")
        return int(payload["patient_id"])

    # --------------------------------------------------
    # RESULTS
    # --------------------------------------------------

    def list_released_results(self, patient_id: int) -> list[dict]:
        results = (
            self.db.query(TestResult)
            .filter(
                TestResult.patient_id == patient_id,
                TestResult.status == ResultStatus.released,
            )
            .order_by(TestResult.created_at.desc())
            .limit(50)
            .all()
        )
        return [self._serialize_result(r) for r in results]

    def get_released_result(self, patient_id: int, result_id: int) -> TestResult:
        r = (
            self.db.query(TestResult)
            .filter(
                TestResult.id == result_id,
                TestResult.patient_id == patient_id,
                TestResult.status == ResultStatus.released,
            )
            .first()
        )
        if not r:
            raise HTTPException(status_code=404, detail="Result not found or not yet released.")
        return r

    def get_patient_profile(self, patient_id: int) -> dict:
        patient = self.db.query(Patient).filter(Patient.id == patient_id).first()
        if not patient:
            raise HTTPException(status_code=404, detail="Patient not found.")

        total_results = (
            self.db.query(TestResult)
            .filter(
                TestResult.patient_id == patient_id,
                TestResult.status == ResultStatus.released,
            )
            .count()
        )

        # SSDO disease history
        from app.services.ssdo.query_engine import SSDOQueryEngine
        disease_history = SSDOQueryEngine(self.db).get_patient_disease_history(patient_id)

        return {
            "patient_id": patient.id,
            "patient_no": patient.patient_no,
            "full_name": patient.full_name,
            "phone": patient.phone,
            "gender": patient.gender,
            "date_of_birth": patient.date_of_birth.isoformat()
                if patient.date_of_birth else None,
            "total_released_results": total_results,
            "disease_history": disease_history,
        }

    # --------------------------------------------------
    # QR RESULT VERIFICATION
    # --------------------------------------------------

    def verify_result_by_sync_id(self, sync_id: str) -> dict:
        """
        Used when a patient or doctor scans the QR code on a PDF.
        Returns the result summary if it's released and verifiable.
        """
        result = (
            self.db.query(TestResult)
            .filter(
                TestResult.sync_id == sync_id,
                TestResult.status == ResultStatus.released,
            )
            .first()
        )

        if not result:
            raise HTTPException(
                status_code=404,
                detail="Result not found or not yet released. "
                       "Please contact the laboratory for assistance."
            )

        return {
            "verified": True,
            "result_id": result.id,
            "sync_id": result.sync_id,
            "status": "released",
            **self._serialize_result(result),
        }

    # --------------------------------------------------
    # BRUTE-FORCE PROTECTION
    # --------------------------------------------------

    def _check_lockout(self, phone: str, ip: Optional[str] = None) -> None:
        record = self._get_attempt_record(phone)
        if not record:
            return
        if record.locked_until and record.locked_until > datetime.utcnow():
            remaining = int((record.locked_until - datetime.utcnow()).total_seconds() / 60)
            raise HTTPException(
                status_code=429,
                detail=f"Too many failed attempts. Account locked for {remaining} more minute(s)."
            )

    def _record_failed_attempt(self, phone: str, ip: Optional[str] = None) -> None:
        record = self._get_attempt_record(phone)
        now = datetime.utcnow()

        if not record:
            record = PortalAuthAttempt(phone=phone, ip_address=ip, attempt_count=0)
            self.db.add(record)

        record.attempt_count += 1
        record.last_attempt = now
        record.ip_address = ip

        if record.attempt_count >= self.max_fails:
            record.locked_until = now + timedelta(minutes=self.lock_minutes)

        self.db.commit()

    def _reset_attempts(self, phone: str) -> None:
        record = self._get_attempt_record(phone)
        if record:
            record.attempt_count = 0
            record.locked_until = None
            self.db.commit()

    def _get_attempt_record(self, phone: str) -> Optional[PortalAuthAttempt]:
        return (
            self.db.query(PortalAuthAttempt)
            .filter(PortalAuthAttempt.phone == phone)
            .first()
        )

    # --------------------------------------------------
    # TOKEN SIGNING
    # --------------------------------------------------

    def _sign(self, payload: dict) -> str:
        raw = json.dumps(payload, separators=(",", ":"), sort_keys=True).encode("utf-8")
        sig = hmac.new(self.secret, raw, hashlib.sha256).digest()
        return (
            base64.urlsafe_b64encode(raw).decode().rstrip("=")
            + "."
            + base64.urlsafe_b64encode(sig).decode().rstrip("=")
        )

    def _verify(self, token: str) -> dict:
        try:
            raw_b64, sig_b64 = token.split(".", 1)
            raw = base64.urlsafe_b64decode(raw_b64 + "==")
            sig = base64.urlsafe_b64decode(sig_b64 + "==")
        except Exception:
            raise HTTPException(status_code=401, detail="Invalid token format.")

        expected = hmac.new(self.secret, raw, hashlib.sha256).digest()
        if not hmac.compare_digest(sig, expected):
            raise HTTPException(status_code=401, detail="Token signature invalid.")

        try:
            return json.loads(raw.decode("utf-8"))
        except Exception:
            raise HTTPException(status_code=401, detail="Token payload corrupt.")

    # --------------------------------------------------
    # SERIALIZER
    # --------------------------------------------------

    def _serialize_result(self, result: TestResult) -> dict:
        test_name = ""
        if result.test_type:
            test_name = result.test_type.name

        # SSDO disease tags for this result
        from app.models.ssdo_index import SSDOIndex
        ssdo = (
            self.db.query(SSDOIndex)
            .filter(
                SSDOIndex.record_type == "test_result",
                SSDOIndex.record_id == result.id,
            )
            .first()
        )

        return {
            "id": result.id,
            "sync_id": result.sync_id,
            "test_type_id": result.test_type_id,
            "test_name": test_name,
            "test_category": ssdo.test_category if ssdo else None,
            "status": result.status.value
                if hasattr(result.status, "value") else str(result.status),
            "created_at": result.created_at.isoformat() if result.created_at else None,
            "created_at_display": result.created_at.strftime("%d %b %Y") if result.created_at else "-",
            "created_at_full_display": result.created_at.strftime("%d %B %Y, %I:%M %p") if result.created_at else "—",
            "disease_tags": ssdo.disease_tags if ssdo else [],
            "severity_flag": ssdo.severity_flag if ssdo else "unknown",
            "sas_assisted": bool(result.sas_predictions),
            "download_url": f"/api/portal/results/{result.id}/pdf",
            "verify_url": f"/api/portal/verify/{result.sync_id}",
        }