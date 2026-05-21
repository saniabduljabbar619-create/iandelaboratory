# -*- coding: utf-8 -*-
# app/utils/lab_no_generator.py

from datetime import datetime
from sqlalchemy.orm import Session

from app.models.lab_report_counter import LabReportCounter


# ── Seed values: last known number per year ───────────────────────────────────
# Update this when migrating to a new year so the sequence picks up correctly.
YEAR_SEEDS = {
    26: 5112,   # ← last lab no issued before this system took over
}


def next_lab_no(db: Session) -> str:
    """
    Generates yearly-resetting LAB numbers.

    Example:
        26-5878
        26-5879
        27-0001  (new year resets to 1 unless a seed is set)
    """

    year_yy = int(datetime.now().strftime("%y"))

    row = (
        db.query(LabReportCounter)
        .filter(LabReportCounter.year == year_yy)
        .with_for_update()
        .first()
    )

    if not row:
        # Start from seed if defined, otherwise from 1
        seed = YEAR_SEEDS.get(year_yy, 0)
        row  = LabReportCounter(
            year=year_yy,
            last_number=seed + 1,
        )
        db.add(row)

    else:
        row.last_number += 1

    db.commit()
    db.refresh(row)

    return f"{year_yy}-{row.last_number:04d}"