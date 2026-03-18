from typing import Optional, List, Tuple
from sqlalchemy.orm import Session
from sqlalchemy import desc

from app.models.test_result import TestResult  # adjust if your model name differs

class ResultRepo:
    def __init__(self, db: Session):
        self.db = db

    # ... your existing methods

    def list_results(
        self,
        patient_id: Optional[int] = None,
        status: Optional[str] = None,
        limit: int = 50,
        offset: int = 0,
    ) -> Tuple[List[TestResult], int]:
        q = self.db.query(TestResult)

        if patient_id is not None:
            q = q.filter(TestResult.patient_id == patient_id)

        if status:
            q = q.filter(TestResult.status == status)

        total = q.count()

        rows = (
            q.order_by(desc(TestResult.created_at))
             .offset(offset)
             .limit(limit)
             .all()
        )
        return rows, total
