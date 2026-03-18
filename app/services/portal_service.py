# -*- coding: utf-8 -*-
from __future__ import annotations

import hmac
import hashlib
import base64
import json
from datetime import datetime, timedelta, timezone

from fastapi import HTTPException
from sqlalchemy.orm import Session
from app.models.test_request import TestRequest
from app.models.patient import Patient
from app.models.test_result import TestResult, ResultStatus
from sqlalchemy.orm import joinedload

class PortalService:
    """
    Minimal portal auth:
    - username = phone
    - password = patient_no
    - token is HMAC-signed payload {patient_id, exp}
    """

    def __init__(self, db: Session, secret: str):
        self.db = db
        self.secret = secret.encode("utf-8")

    def login(self, phone: str, patient_no: str) -> dict:
        p = (
            self.db.query(Patient)
            .filter(Patient.phone == phone, Patient.patient_no == patient_no)
            .first()
        )
        if not p:
            raise HTTPException(status_code=401, detail="Invalid credentials")

        exp = datetime.now(timezone.utc) + timedelta(minutes=15)
        payload = {"patient_id": p.id, "exp": int(exp.timestamp())}
        token = self._sign(payload)
        return {"token": token, "expires_at": exp}


    def list_released_results(self, patient_id: int) -> list[TestResult]:

        return (
            self.db.query(TestResult)
            .filter(
                TestResult.patient_id == patient_id,
                TestResult.status == ResultStatus.released
            )
            .order_by(TestResult.created_at.desc())
            .limit(50)
            .all()
        )
    
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
            raise HTTPException(status_code=404, detail="Result not found")

        return r

    def verify_token(self, token: str) -> int:
        payload = self._verify(token)
        if payload["exp"] < int(datetime.now(timezone.utc).timestamp()):
            raise HTTPException(status_code=401, detail="Token expired")
        return int(payload["patient_id"])

    def _sign(self, payload: dict) -> str:
        raw = json.dumps(payload, separators=(",", ":"), sort_keys=True).encode("utf-8")
        sig = hmac.new(self.secret, raw, hashlib.sha256).digest()
        return base64.urlsafe_b64encode(raw).decode().rstrip("=") + "." + base64.urlsafe_b64encode(sig).decode().rstrip("=")

    def _verify(self, token: str) -> dict:
        try:
            raw_b64, sig_b64 = token.split(".", 1)
            raw = base64.urlsafe_b64decode(raw_b64 + "==")
            sig = base64.urlsafe_b64decode(sig_b64 + "==")
        except Exception:
            raise HTTPException(status_code=401, detail="Invalid token")

        expected = hmac.new(self.secret, raw, hashlib.sha256).digest()
        if not hmac.compare_digest(sig, expected):
            raise HTTPException(status_code=401, detail="Invalid token")

        try:
            payload = json.loads(raw.decode("utf-8"))
            return payload
        except Exception:
            raise HTTPException(status_code=401, detail="Invalid token")