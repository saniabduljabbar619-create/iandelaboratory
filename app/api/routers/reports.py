# app/api/routers/reports.py
from fastapi import APIRouter, Depends, Query, HTTPException
from sqlalchemy.orm import Session

from app.api.deps import get_db
from app.core.dependencies import get_current_user
from app.services.report_service import ReportService
from app.models.user import User # Ensure User is imported for type hinting

router = APIRouter()

# --- MANAGEMENT REPORTS (Existing) ---
@router.get("/generate")
def generate_report(
    date_from: str = Query(...),
    date_to: str = Query(...),
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    svc = ReportService(db, current_user.branch_id)
    data = svc.generate(date_from, date_to)
    return data

# --- CLINICAL REPORTS (New for Step 7.5) ---
@router.get("/clinical/{request_id}")
def get_clinical_report(
    request_id: int, 
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """
    Fetches the 'Source of Truth' for the Lab App's 
    individual patient report view.
    """
    service = ReportService(db)
    report_data = service.get_patient_clinical_report(request_id)
    
    if not report_data:
        raise HTTPException(status_code=404, detail="Report not found")
        
    return report_data

@router.get("/management/summary")
def get_management_summary(
    date_from: str, 
    date_to: str, 
    branch_id: int | None = None,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """
    Fetches the financial/stats summary for the Admin Dashboard.
    """
    service = ReportService(db, branch_id=branch_id)
    return service.generate(date_from, date_to)