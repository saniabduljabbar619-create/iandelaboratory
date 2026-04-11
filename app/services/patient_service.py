# -*- coding: utf-8 -*-
from __future__ import annotations

from datetime import datetime, timedelta, timezone
from fastapi import HTTPException
from sqlalchemy.orm import Session
from sqlalchemy import or_, func
from sqlalchemy.exc import IntegrityError

from app.models.patient import Patient
from app.schemas.patient import PatientCreate, PatientUpdate
from app.core.branch_scope import resolve_branch_scope


class PatientService:
    # Enterprise Format: IEL-YY-NNNN
    PREFIX = "IEL"
    PAD = 4  

    def __init__(self, db: Session, current_user, requested_branch_id: int | None = None):
        self.db = db
        self.current_user = current_user
        self.branch_id = resolve_branch_scope(current_user, requested_branch_id)

    def _next_patient_no(self) -> str:
        """
        Generates the next sequential Lab ID.
        Flow:
        - First 2026 entry: IEL-26-3150
        - Next: IEL-26-3151
        - Jan 1 2027: IEL-27-0001
        """
        # 1. Get current year suffix (e.g., '26')
        now = datetime.now()
        current_year_yy = now.strftime("%y") 
        year_prefix = f"{self.PREFIX}-{current_year_yy}-"

        # 2. Find the highest number for the current year prefix
        # We use 'with_for_update' to prevent race conditions during high-volume registration
        last = (
            self.db.query(Patient)
            .filter(Patient.patient_no.like(f"{year_prefix}%"))
            .order_by(Patient.patient_no.desc())
            .with_for_update()
            .first()
        )

        if not last:
            # Check if we are starting the 2026 sequence
            if current_year_yy == "26":
                nxt = 3500
            else:
                # Standard New Year reset
                nxt = 1
        else:
            # Parse the numeric tail after the last dash
            try:
                parts = last.patient_no.split("-")
                nxt = int(parts[-1]) + 1
            except (ValueError, IndexError):
                nxt = 1

        return f"{year_prefix}{nxt:0{self.PAD}d}"

    def create(self, payload: PatientCreate) -> Patient:
        data = payload.model_dump()

        # 1. Handle patient_no generation
        patient_no = (data.get("patient_no") or "").strip()
        if not patient_no:
            patient_no = self._next_patient_no()
            data["patient_no"] = patient_no

        # 2. THE FIX: If branch_id is in the payload (from Sync Engine), use it!
        # Otherwise, fall back to the user's resolved scope.
        if data.get("branch_id") is None:
            data["branch_id"] = self.branch_id

        # 3. Double check for duplicates
        exists = self.db.query(Patient).filter(Patient.patient_no == patient_no).first()
        if exists:
            raise HTTPException(status_code=400, detail="Patient number already exists")

        try:
            p = Patient(**data)
            self.db.add(p)
            self.db.commit()
            self.db.refresh(p)
            return p
        except IntegrityError as e:
            self.db.rollback()
            # Log the actual error to Render logs so we can see which column failed
            print(f"DEBUG: IntegrityError during create: {str(e)}") 
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
        Search by query string (Name, Phone, ID) or filter by specific date.
        """
        query = self.db.query(Patient)

        if self.branch_id:
            query = query.filter(Patient.branch_id == self.branch_id)

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
                day = datetime.strptime(created_date, "%Y-%m-%d")
                tz_offset = timezone(timedelta(hours=1)) # Nigeria UTC+1

                start_local = day.replace(hour=0, minute=0, second=0, microsecond=0, tzinfo=tz_offset)
                end_local = start_local + timedelta(days=1)

                # Convert to naive UTC for DB comparison
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
        
        return []
