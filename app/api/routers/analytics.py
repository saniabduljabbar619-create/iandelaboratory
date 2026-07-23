# -*- coding: utf-8 -*-
# app/api/routers/analytics.py
from __future__ import annotations

from datetime import date, timedelta
from typing import Optional

from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session

from app.api.deps import get_db, get_current_user_claims
from app.services.analytics.snapshot_service import SnapshotService

router = APIRouter(prefix="/api/analytics", tags=["analytics"])


def _svc(db: Session, claims: dict) -> SnapshotService:
    branch_id = claims.get("branch_id") or None
    return SnapshotService(db, branch_id=branch_id)


def _current_week_start() -> date:
    today = date.today()
    return today - timedelta(days=today.weekday())


# --------------------------------------------------
# SNAPSHOT ENDPOINTS
# --------------------------------------------------

@router.post("/snapshot/weekly")
def generate_weekly_snapshot(
    week_start: Optional[date] = Query(default=None),
    db: Session = Depends(get_db),
    claims: dict = Depends(get_current_user_claims),
):
    """
    Generate or regenerate the weekly analytics snapshot.
    Defaults to the current week if no date provided.
    Idempotent — safe to run multiple times.
    """
    target_week = week_start or _current_week_start()
    svc = _svc(db, claims)
    snapshot = svc.build_weekly_snapshot(target_week)
    return {
        "message": f"Weekly snapshot generated for {snapshot.period_start} → {snapshot.period_end}",
        "snapshot_id": snapshot.id,
        "period_start": snapshot.period_start.isoformat(),
        "period_end": snapshot.period_end.isoformat(),
        "total_tests": snapshot.total_tests,
        "total_patients": snapshot.total_patients,
        "total_revenue": float(snapshot.total_revenue),
        "abnormal_results_count": snapshot.abnormal_results_count,
        "critical_results_count": snapshot.critical_results_count,
        "top_tests": snapshot.top_tests,
        "top_disease_tags": snapshot.top_disease_tags,
    }


@router.get("/snapshot/latest")
def get_latest_snapshot(
    snapshot_type: str = Query(default="weekly"),
    db: Session = Depends(get_db),
    claims: dict = Depends(get_current_user_claims),
):
    """Returns the most recent analytics snapshot."""
    svc = _svc(db, claims)
    snap = svc.get_latest_snapshot(snapshot_type)
    if not snap:
        return {"message": "No snapshots found. Run POST /api/analytics/snapshot/weekly first."}
    return snap


@router.get("/snapshot/history")
def snapshot_history(
    snapshot_type: str = Query(default="weekly"),
    limit: int = Query(default=12),
    db: Session = Depends(get_db),
    claims: dict = Depends(get_current_user_claims),
):
    """Returns historical snapshots, newest first."""
    svc = _svc(db, claims)
    return svc.list_snapshots(snapshot_type, limit)


# --------------------------------------------------
# DISEASE TREND ENDPOINTS
# --------------------------------------------------

@router.post("/trends/weekly")
def generate_weekly_trends(
    week_start: Optional[date] = Query(default=None),
    db: Session = Depends(get_db),
    claims: dict = Depends(get_current_user_claims),
):
    """
    Generate disease trend data for the specified week.
    Compares to the previous week to compute rising/falling/stable.
    """
    target_week = week_start or _current_week_start()
    svc = _svc(db, claims)
    trends = svc.build_disease_trends(target_week)
    return {
        "week_start": target_week.isoformat(),
        "disease_count": len(trends),
        "trends": [
            {
                "disease_tag": t.disease_tag,
                "test_category": t.test_category,
                "occurrence_count": t.occurrence_count,
                "critical_count": t.critical_count,
                "affected_patient_count": t.affected_patient_count,
                "trend_direction": t.trend_direction,
                "previous_week_count": t.previous_week_count,
            }
            for t in sorted(trends, key=lambda x: x.occurrence_count, reverse=True)
        ],
    }


@router.get("/trends/weekly")
def get_weekly_trends(
    week_start: Optional[date] = Query(default=None),
    limit: int = Query(default=20),
    db: Session = Depends(get_db),
    claims: dict = Depends(get_current_user_claims),
):
    """Returns stored disease trend data, newest week first."""
    svc = _svc(db, claims)
    trends = svc.get_weekly_trends(week_start, limit)
    if not trends:
        return {"message": "No trend data found. Run POST /api/analytics/trends/weekly first."}
    return trends