# -*- coding: utf-8 -*-
# app/utils/lab_no_generator.py

from datetime import datetime
from sqlalchemy.orm import Session

from app.models.lab_report_counter import LabReportCounter


def next_lab_no(db: Session) -> str:
    """
    Generates yearly-resetting LAB numbers.

    Example:
        26-0001
        26-0002
        26-5599

    Resets automatically every new year.
    """

    year_yy = int(datetime.now().strftime("%y"))

    row = (
        db.query(LabReportCounter)
        .filter(LabReportCounter.year == year_yy)
        .with_for_update()
        .first()
    )

    if not row:
        row = LabReportCounter(
            year=year_yy,
            last_number=1,
        )

        db.add(row)
        db.commit()
        db.refresh(row)

    else:
        row.last_number += 1

        db.commit()
        db.refresh(row)

    return f"{year_yy}-{row.last_number:04d}"