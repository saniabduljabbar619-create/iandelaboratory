from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.db.session import get_db
from app.models.test_request import TestRequest
from app.models.patient import Patient
from app.models.test_result import TestResult, ResultStatus
from app.schemas.test_result import ResultInstantiateFromSnapshot, TestResultOut
from app.services.compute_service import ComputeService

router = APIRouter(prefix="/api/test-results", tags=["test-results"])

@router.post("/from-snapshot", response_model=TestResultOut)
def create_from_snapshot(payload: ResultInstantiateFromSnapshot, db: Session = Depends(get_db)):
    if not payload.template_snapshot:
        raise HTTPException(status_code=400, detail="template_snapshot is required")

    flags = ComputeService.compute_flags(payload.template_snapshot, payload.values)

    row = TestResult(
        patient_id=payload.patient_id,
        test_type_id=payload.test_type_id,
        template_id=payload.template_id,  # may be None if you applied the nullable change
        status=ResultStatus.draft,
        template_snapshot=payload.template_snapshot,
        values=payload.values,
        flags=flags,
        notes=payload.notes,
    )

    db.add(row)
    db.commit()
    db.refresh(row)
    return row