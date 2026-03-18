# -*- coding: utf-8 -*-
# app/services/patient_service.py
from __future__ import annotations

from fastapi import HTTPException
from sqlalchemy.orm import Session
from sqlalchemy import or_
from sqlalchemy.exc import IntegrityError

from app.models.patient import Patient
from app.schemas.patient import PatientCreate, PatientUpdate
from app.core.branch_scope import resolve_branch_scope


class PatientService:
    PREFIX = "LPT-"
    PAD = 4  # LPT-0001

    def __init__(self, db: Session, current_user, requested_branch_id: int | None = None):
        self.db = db
        self.current_user = current_user
        self.branch_id = resolve_branch_scope(current_user, requested_branch_id)


    def _next_patient_no(self) -> str:
        """
        Generate next LPT-0001 style number.
        We lock the last row to avoid two requests generating the same number.
        """
        last = (
            self.db.query(Patient)
            .order_by(Patient.id.desc())
            .with_for_update()          # important: serializes number generation
            .first()
        )

        if not last or not (last.patient_no or "").startswith(self.PREFIX):
            nxt = 1
        else:
            # parse numeric tail safely
            tail = (last.patient_no or "")[len(self.PREFIX):]
            try:
                nxt = int(tail) + 1
            except ValueError:
                nxt = 1

        return f"{self.PREFIX}{nxt:0{self.PAD}d}"

    def create(self, payload: PatientCreate) -> Patient:
        data = payload.model_dump()

        patient_no = (data.get("patient_no") or "").strip()
        if not patient_no:
            patient_no = self._next_patient_no()
            data["patient_no"] = patient_no

        # ✅ Attach branch_id (CRITICAL FIX)
        data["branch_id"] = self.branch_id

        exists = self.db.query(Patient).filter(Patient.patient_no == patient_no).first()
        if exists:
            raise HTTPException(status_code=400, detail="Patient number already exists")

        print("PATIENT CREATE PAYLOAD:", data)

        try:
            p = Patient(**data)
            self.db.add(p)
            self.db.commit()
            self.db.refresh(p)
            return p
        except IntegrityError as e:
            self.db.rollback()
            print("INTEGRITY ERROR:", e)
            raise HTTPException(status_code=400, detail="Database integrity error")

    def get(self, patient_id: int) -> Patient:
        query = self.db.query(Patient).filter(Patient.id == patient_id)

        if self.branch_id:
            query = query.filter(Patient.branch_id == self.branch_id)

        p = query.first()

        if not p:
            raise HTTPException(status_code=404, detail="Patient not found")

        return p


    def update(self, patient_id: int, payload: PatientUpdate) -> Patient:
        p = self.get(patient_id)
        data = payload.model_dump(exclude_unset=True)
        for k, v in data.items():
            setattr(p, k, v)
        self.db.commit()
        self.db.refresh(p)
        return p

    def search(self, q: str) -> list[Patient]:
        q = q.strip()
        if not q:
            return []

        query = self.db.query(Patient)

        if self.branch_id:
            query = query.filter(Patient.branch_id == self.branch_id)

        return (
            query.filter(
                or_(
                    Patient.full_name.like(f"%{q}%"),
                    Patient.phone.like(f"%{q}%"),
                    Patient.patient_no.like(f"%{q}%"),
                )
            )
            .order_by(Patient.id.desc())
            .limit(50)
            .all()
        )

