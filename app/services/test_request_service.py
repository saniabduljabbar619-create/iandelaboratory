# -*- coding: utf-8 -*-
# app/services/test_request_service.py

from __future__ import annotations

from datetime import datetime
from fastapi import HTTPException
from sqlalchemy import func
from sqlalchemy.orm import Session
from app.core.branch_scope import resolve_branch_scope
from app.models.test_type import TestType
from app.models.test_request import TestRequest
from app.models.patient import Patient 
from app.schemas.test_request import TestRequestCreate, TestRequestStatusUpdate


class TestRequestService:
    
    def __init__(self, db: Session, current_user, requested_branch_id: int | None = None):
        self.db = db
        self.current_user = current_user
        self.branch_id = resolve_branch_scope(current_user, requested_branch_id)


    def create(self, payload: TestRequestCreate) -> TestRequest:
        effective_branch_id = payload.branch_id if hasattr(payload, 'branch_id') and payload.branch_id else self.branch_id

        if not effective_branch_id:
            raise HTTPException(status_code=400, detail="Branch context required")

        tr = TestRequest(
            sync_id=payload.sync_id, 
            patient_id=payload.patient_id,
            test_type_id=payload.test_type_id,
            requested_by=payload.requested_by,
            requested_note=payload.requested_note,
            status=payload.status or "pending", 
            branch_id=effective_branch_id,
        )

        self.db.add(tr)
        try:
            self.db.commit()
            self.db.refresh(tr)
            return tr
        except Exception as e:
            self.db.rollback()
            print(f"DEBUG: Error creating test request: {str(e)}")
            raise HTTPException(status_code=400, detail="Database integrity error")

    def list(
        self,
        status: str | None = None,
        patient_id: int | None = None,
        created_date: str | None = None,  # 🔥 Added date filter support
        limit: int = 50
    ):
        # Join all three tables to get the full picture
        q = (
            self.db.query(TestRequest, TestType, Patient)
            .join(TestType, TestType.id == TestRequest.test_type_id)
            .join(Patient, Patient.id == TestRequest.patient_id)
        )

        if self.branch_id:
            q = q.filter(TestRequest.branch_id == self.branch_id)

        if status:
            q = q.filter(TestRequest.status == status)

        if patient_id:
            q = q.filter(TestRequest.patient_id == patient_id)

        # 🔥 Filter by specific day (YYYY-MM-DD)
        if created_date:
            q = q.filter(func.date(TestRequest.created_at) == created_date)

        rows = q.order_by(TestRequest.created_at.desc()).limit(limit).all()

        out = []

        for tr, tt, p in rows: 
            out.append({
                "id": tr.id,
                "patient_id": tr.patient_id,
                "test_type_id": tr.test_type_id,
                "status": tr.status,
                "requested_by": tr.requested_by,
                "created_at": tr.created_at,
                "updated_at": tr.updated_at,
                
                # 🔥 Nested Patient Data for Frontend Compatibility
                # This allows the Daily Queue to show old patients with new requests
                "patient": {
                    "id": p.id,
                    "patient_no": p.patient_no,
                    "full_name": p.full_name,
                    "phone": p.phone,
                    "gender": p.gender,
                    "dob": p.date_of_birth.isoformat() if p.date_of_birth else None,
                    "created_at": p.created_at
                },

                # 🔥 Test Info Enrichment
                "test_name": tt.name,
                "price": float(tt.price) if tt.price else 0.0,
            })

        return out

    def get(self, request_id: int) -> TestRequest:
        q = self.db.query(TestRequest).filter(TestRequest.id == request_id)
        if self.branch_id:
            q = q.filter(TestRequest.branch_id == self.branch_id)

        tr = q.first()
        if not tr:
            raise HTTPException(status_code=404, detail="Test request not found")
        return tr


    def update_status(self, request_id: int, payload: TestRequestStatusUpdate) -> TestRequest:
        tr = self.get(request_id)

        allowed = {
            "pending": {"paid", "rejected"},
            "paid": {"accepted", "rejected"},
            "accepted": {"fulfilled", "in_progress"}, # Added in_progress for lab flow
            "rejected": set(),
            "fulfilled": set(),
        }

        if payload.status != tr.status and payload.status not in allowed.get(tr.status, set()):
            raise HTTPException(status_code=400, detail=f"Invalid transition {tr.status} -> {payload.status}")

        tr.status = payload.status

        if payload.status == "accepted" and tr.accepted_at is None:
            tr.accepted_at = datetime.utcnow()

        if payload.status == "fulfilled" and tr.fulfilled_at is None:
            tr.fulfilled_at = datetime.utcnow()

        if payload.test_result_id:
            tr.test_result_id = payload.test_result_id

        self.db.commit()
        self.db.refresh(tr)
        return tr
