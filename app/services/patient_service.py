# -*- coding: utf-8 -*-
# app/services/patient_service.py
from __future__ import annotations

from datetime import datetime
from fastapi import HTTPException
from sqlalchemy.orm import Session
from sqlalchemy import or_, func  # Added func for date extraction
from sqlalchemy.exc import IntegrityError
from datetime import datetime, timedelta, timezone
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

    def search(self, q: str | None = None, created_date: str | None = None) -> list[Patient]:
            """
            Search by query string OR filter by creation date (Daily Queue).
            """
            query = self.db.query(Patient)
    
            # 1. Apply Branch Scope
            if self.branch_id:
                query = query.filter(Patient.branch_id == self.branch_id)
    
            # 2. Logic for Global Search
            if q and q.strip():
                search_str = q.strip()
                return (
                    query.filter(
                        or_(
                            Patient.full_name.ilike(f"%{search_str}%"),
                            Patient.phone.ilike(f"%{search_str}%"),
                            Patient.patient_no.ilike(f"%{search_str}%"),
                        )
                    )
                    .order_by(Patient.id.desc())
                    .limit(50)
                    .all()
                )
    
    
            if created_date:
                try:
                    # Parse date from frontend (assumed local time)
                    day = datetime.strptime(created_date, "%Y-%m-%d")
    
                    # Nigeria timezone (UTC+1)
                    tz_offset = timezone(timedelta(hours=1))
    
                    # Make it timezone-aware
                    start_local = day.replace(
                        hour=0, minute=0, second=0, microsecond=0, tzinfo=tz_offset
                    )
                    end_local = start_local + timedelta(days=1)
    
                    # Convert to UTC (what DB should use)
                    start_utc = start_local.astimezone(timezone.utc).replace(tzinfo=None)
                    end_utc = end_local.astimezone(timezone.utc).replace(tzinfo=None)
    
                    return (
                        query.filter(Patient.created_at >= start_utc)
                        .filter(Patient.created_at < end_utc)
                        .order_by(Patient.created_at.asc())
                        .all()
                    )
    
                except ValueError:
                    return []
