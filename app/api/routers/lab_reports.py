# -*- coding: utf-8 -*-

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.api.deps import get_db
from app.utils.lab_no_generator import next_lab_no

router = APIRouter(
    prefix="/lab-reports",
    tags=["Lab Reports"]
)


@router.post("/next-lab-no")
def generate_lab_no(
    db: Session = Depends(get_db)
):
    """
    Generates the next yearly LAB number.

    Example:
        26-0001
        26-0002
    """

    lab_no = next_lab_no(db)

    return {
        "success": True,
        "lab_no": lab_no
    }