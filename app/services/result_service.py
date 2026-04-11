# -*- coding: utf-8 -*-
#app/services/result_service.py
from __future__ import annotations

from typing import Optional, Tuple, List

from fastapi import HTTPException
from sqlalchemy.orm import Session
from sqlalchemy import desc

from app.models.patient import Patient
from app.models.test_template import TestTemplate
from app.models.test_result import TestResult, ResultStatus
from app.schemas.test_result import ResultInstantiate, ResultUpdateValues, ResultInstantiateFromSnapshot
from app.services.compute_service import ComputeService
from app.services.audit_service import AuditService
from app.core.branch_scope import resolve_branch_scope
from app.services.notification_service import NotificationService
from app.models.patient import Patient

class ResultService:
    def __init__(self, db: Session, current_user, requested_branch_id: int | None = None):
        self.db = db
        self.current_user = current_user
        self.branch_id = resolve_branch_scope(current_user, requested_branch_id)


    def instantiate(self, payload: ResultInstantiate) -> TestResult:
        if not self.branch_id:
            raise HTTPException(status_code=400, detail="User not bound to branch")
        patient_query = self.db.query(Patient).filter(Patient.id == payload.patient_id)

        if self.branch_id:
            patient_query = patient_query.filter(Patient.branch_id == self.branch_id)

        patient = patient_query.first()

        if not patient:
            raise HTTPException(status_code=404, detail="Patient not found")

        if not patient:
            raise HTTPException(status_code=404, detail="Patient not found")

        template = self.db.query(TestTemplate).filter(TestTemplate.id == payload.template_id).first()
        if not template:
            raise HTTPException(status_code=404, detail="Template not found")
        if not template.is_active:
            raise HTTPException(status_code=400, detail="Template is not active")

        # test_type_id is derived from template (correct design)
        r = TestResult(
            patient_id=patient.id,
            test_type_id=template.test_type_id,
            template_id=template.id,
            status=ResultStatus.draft,
            template_snapshot=template.structure,  # snapshot
            values={},
            flags={},
            notes=None,
            branch_id=self.branch_id,  # ✅ CRITICAL
        )
        self.db.add(r)
        self.db.commit()
        self.db.refresh(r)
        return r
    
    def instantiate_from_snapshot(self, payload: ResultInstantiateFromSnapshot) -> TestResult:
        # ✅ THE FIX: Prioritize branch_id from payload (for sync)
        # Fall back to self.branch_id (resolved from current user)
        effective_branch_id = payload.branch_id if hasattr(payload, 'branch_id') and payload.branch_id else self.branch_id

        # Strict check: Fail if we still have no branch ID
        if not effective_branch_id:
            raise HTTPException(status_code=400, detail="User not bound to branch")
        
        # Branch-aware Patient lookup
        patient_query = self.db.query(Patient).filter(Patient.id == payload.patient_id)
        if effective_branch_id:
            patient_query = patient_query.filter(Patient.branch_id == effective_branch_id)

        patient = patient_query.first()
        if not patient:
            raise HTTPException(status_code=404, detail="Patient not found")

        snapshot = payload.template_snapshot if isinstance(payload.template_snapshot, dict) else {}
        if not snapshot:
            raise HTTPException(status_code=400, detail="template_snapshot is required")

        values = payload.values if isinstance(payload.values, dict) else {}
        flags = ComputeService.compute_flags(snapshot, values)

        r = TestResult(
            sync_id=payload.sync_id,  # ✅ Map the UUID
            patient_id=patient.id,
            test_type_id=payload.test_type_id,
            template_id=payload.template_id,
            status=payload.status or ResultStatus.draft,
            template_snapshot=snapshot,
            values=values,
            flags=flags,
            notes=payload.notes,
            branch_id=effective_branch_id,  # ✅ Use the effective branch
        )

        self.db.add(r)
        self.db.commit()
        self.db.refresh(r)

        AuditService(self.db).log(
            actor_type="system" if payload.sync_id else "staff",
            actor="sync_engine" if payload.sync_id else "labtech",
            action="instantiate",
            entity="test_result",
            entity_id=r.id,
            ip=None,
            meta={"source": "snapshot", "status": r.status.value},
        )

        return r

    def get(self, result_id: int) -> TestResult:
        r = self.db.query(TestResult).filter(TestResult.id == result_id).first()
        if not r:
            raise HTTPException(status_code=404, detail="Result not found")
        return r

    def update_values(self, result_id: int, payload: ResultUpdateValues) -> TestResult:

        r = self.get(result_id)

        existing = r.values if isinstance(r.values, dict) else {}
        incoming = payload.values if isinstance(payload.values, dict) else {}
        merged = {**existing, **incoming}

        r.values = merged
        r.flags = ComputeService.compute_flags(r.template_snapshot, merged)

        if payload.notes is not None:
            r.notes = payload.notes

        # Result remains draft until cashier releases
        if r.status == ResultStatus.draft:
            r.status = ResultStatus.draft

        self.db.commit()
        self.db.refresh(r)

        return r

    def set_status(self, result_id: int, new_status: str, role: str) -> TestResult:
        r = self.get(result_id)

        role = (role or "").lower().strip()
        new_status = (new_status or "").lower().strip()

        try:
            new_enum = ResultStatus(new_status)
        except Exception:
            raise HTTPException(status_code=400, detail=f"Invalid status: {new_status}")

        allowed = {
            "labtech": {
                "draft": {"in_progress"},
                "in_progress": {"pending_review"},
            },
            "supervisor": {
                "pending_review": {"approved"},
                "approved": {"released"},
            },
            "admin": {
                "draft": {"released"},
                "in_progress": {"released"},
                "pending_review": {"released"},
                "approved": {"released"},
            },
        }

        if role not in allowed:
            raise HTTPException(status_code=403, detail="Invalid role")

        current = r.status.value if hasattr(r.status, "value") else str(r.status)
        next_allowed = allowed[role].get(current, set())

        if new_status not in next_allowed:
            raise HTTPException(
                status_code=400,
                detail=f"Transition not allowed: {current} -> {new_status} for role {role}",
            )

        r.status = new_enum
        self.db.commit()
        self.db.refresh(r)

        # Audit log
        AuditService(self.db).log(
            actor_type="staff",
            actor=role,
            action="status_change",
            entity="test_result",
            entity_id=r.id,
            ip=None,
            meta={"from": current, "to": new_status},
        )

        # -------------------------------------------------
        # Phase 5: Notification when result is released
        # -------------------------------------------------
        if new_status == "released":

            patient = (
                self.db.query(Patient)
                .filter(Patient.id == r.patient_id)
                .first()
            )

            patient_name = patient.full_name if patient else "Patient"
            phone = patient.phone if patient else None

            # Notification (existing)
            NotificationService.create(
                db=self.db,
                type="result_ready",
                title="Result Ready",
                message=f"Lab result ready for {patient_name}",
                reference_type="test_result",
                reference_id=r.id
            )

            # -----------------------------------
            # SMS DISPATCH (SAFE + OPTIONAL)
            # -----------------------------------
            if phone:
                try:
                    sms_message = (
                        f"I&E Diagnostic Lab:\n"
                        f"Dear {patient_name}, your test result is ready.\n"
                        f"Ref: {r.id}\n"
                        
                        f"For assistance call: 08063645308"
                    )

                    NotificationService.send_sms(
                        phone=phone,
                        message=sms_message
                    )

                except Exception as sms_error:
                    # Do NOT break release flow
                    print(f"[SMS ERROR] {sms_error}")

        return r

    # --- NEW: List results (Option 2 canonical) ---
    def list(
        self,
        patient_id: Optional[int] = None,
        status: Optional[str] = None,
        limit: int = 50,
        offset: int = 0,
        role: str = "labtech",
    ) -> tuple[list[TestResult], int]:
        # Currently permissive for staff roles; tighten later if needed.
        role = (role or "").lower().strip()
        if role not in {"labtech", "labstaff", "cashier", "supervisor", "admin"}:
            raise HTTPException(status_code=403, detail="Invalid role")

        q = self.db.query(TestResult)

        if self.branch_id:
            q = q.filter(TestResult.branch_id == self.branch_id)


        if patient_id is not None:
            q = q.filter(TestResult.patient_id == patient_id)

        if status:
            status_norm = (status or "").lower().strip()
            try:
                status_enum = ResultStatus(status_norm)
            except Exception:
                raise HTTPException(status_code=400, detail=f"Invalid status: {status_norm}")
            q = q.filter(TestResult.status == status_enum)

        total = q.count()
        rows = (
            q.order_by(desc(TestResult.created_at))
             .offset(offset)
             .limit(limit)
             .all()
        )
        return rows, total
