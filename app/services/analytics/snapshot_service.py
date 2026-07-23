# -*- coding: utf-8 -*-
# app/services/analytics/snapshot_service.py
from __future__ import annotations

from datetime import date, datetime, timedelta
from typing import Optional

from sqlalchemy.orm import Session
from sqlalchemy import func

from app.models.analytics import AnalyticsSnapshot, DiseaseWeeklyTrend
from app.models.test_result import TestResult
from app.models.patient import Patient
from app.models.payment import Payment
from app.models.ssdo_index import SSDOIndex


class SnapshotService:

    def __init__(self, db: Session, branch_id: Optional[int] = None):
        self.db = db
        self.branch_id = branch_id

    # --------------------------------------------------
    # WEEKLY SNAPSHOT
    # --------------------------------------------------

    def build_weekly_snapshot(self, week_start: date) -> AnalyticsSnapshot:
        """
        Aggregates all lab activity for the week starting on week_start.
        Idempotent — safe to run multiple times for the same week.
        """
        week_end = week_start + timedelta(days=6)
        start_dt = datetime.combine(week_start, datetime.min.time())
        end_dt = datetime.combine(week_end, datetime.max.time())

        # Remove existing snapshot for this period if it exists
        existing = self.db.query(AnalyticsSnapshot).filter(
            AnalyticsSnapshot.snapshot_type == "weekly",
            AnalyticsSnapshot.period_start == week_start,
            AnalyticsSnapshot.branch_id == self.branch_id,
        ).first()
        if existing:
            self.db.delete(existing)
            self.db.flush()

        # Total tests
        q_tests = self.db.query(TestResult).filter(
            TestResult.created_at.between(start_dt, end_dt)
        )
        if self.branch_id:
            q_tests = q_tests.filter(TestResult.branch_id == self.branch_id)
        total_tests = q_tests.count()

        # Total unique patients who had tests
        q_patients = self.db.query(func.count(func.distinct(TestResult.patient_id))).filter(
            TestResult.created_at.between(start_dt, end_dt)
        )
        if self.branch_id:
            q_patients = q_patients.filter(TestResult.branch_id == self.branch_id)
        total_patients = q_patients.scalar() or 0

        # Revenue
        q_revenue = self.db.query(func.coalesce(func.sum(Payment.amount), 0)).filter(
            Payment.created_at.between(start_dt, end_dt)
        )
        if self.branch_id:
            q_revenue = q_revenue.filter(Payment.branch_id == self.branch_id)
        total_revenue = float(q_revenue.scalar() or 0)

        # Abnormal and critical from SSDO
        q_ssdo = self.db.query(SSDOIndex).filter(
            SSDOIndex.record_type == "test_result",
            SSDOIndex.temporal_position.between(start_dt, end_dt),
        )
        if self.branch_id:
            q_ssdo = q_ssdo.filter(SSDOIndex.branch_id == self.branch_id)
        ssdo_entries = q_ssdo.all()

        abnormal_count = sum(1 for e in ssdo_entries if e.severity_flag == "abnormal")
        critical_count = sum(1 for e in ssdo_entries if e.severity_flag == "critical")

        # Top disease tags
        tag_counts: dict[str, int] = {}
        for e in ssdo_entries:
            if isinstance(e.disease_tags, list):
                for tag in e.disease_tags:
                    tag_counts[tag] = tag_counts.get(tag, 0) + 1
        top_disease_tags = [
            {"tag": tag, "count": cnt}
            for tag, cnt in sorted(tag_counts.items(), key=lambda x: x[1], reverse=True)[:10]
        ]

        # Top test categories
        cat_counts: dict[str, int] = {}
        for e in ssdo_entries:
            cat = e.test_category or "Unknown"
            cat_counts[cat] = cat_counts.get(cat, 0) + 1
        top_tests = [
            {"category": cat, "count": cnt}
            for cat, cnt in sorted(cat_counts.items(), key=lambda x: x[1], reverse=True)[:10]
        ]

        snapshot = AnalyticsSnapshot(
            snapshot_type="weekly",
            period_start=week_start,
            period_end=week_end,
            branch_id=self.branch_id,
            total_tests=total_tests,
            total_patients=total_patients,
            total_revenue=total_revenue,
            abnormal_results_count=abnormal_count,
            critical_results_count=critical_count,
            top_tests=top_tests,
            top_disease_tags=top_disease_tags,
        )
        self.db.add(snapshot)
        self.db.commit()
        self.db.refresh(snapshot)
        return snapshot

    def get_latest_snapshot(self, snapshot_type: str = "weekly") -> Optional[AnalyticsSnapshot]:
        q = self.db.query(AnalyticsSnapshot).filter(
            AnalyticsSnapshot.snapshot_type == snapshot_type
        )
        if self.branch_id:
            q = q.filter(AnalyticsSnapshot.branch_id == self.branch_id)
        return q.order_by(AnalyticsSnapshot.period_start.desc()).first()

    def list_snapshots(
        self,
        snapshot_type: str = "weekly",
        limit: int = 12,
    ) -> list[AnalyticsSnapshot]:
        q = self.db.query(AnalyticsSnapshot).filter(
            AnalyticsSnapshot.snapshot_type == snapshot_type
        )
        if self.branch_id:
            q = q.filter(AnalyticsSnapshot.branch_id == self.branch_id)
        return q.order_by(AnalyticsSnapshot.period_start.desc()).limit(limit).all()

    # --------------------------------------------------
    # WEEKLY DISEASE TRENDS
    # --------------------------------------------------

    def build_disease_trends(self, week_start: date) -> list[DiseaseWeeklyTrend]:
        """
        Aggregates disease tag frequency for the week and computes
        trend direction by comparing to the previous week.
        """
        week_end = week_start + timedelta(days=6)
        prev_week_start = week_start - timedelta(days=7)
        start_dt = datetime.combine(week_start, datetime.min.time())
        end_dt = datetime.combine(week_end, datetime.max.time())
        prev_start_dt = datetime.combine(prev_week_start, datetime.min.time())

        # Delete existing trends for this week
        self.db.query(DiseaseWeeklyTrend).filter(
            DiseaseWeeklyTrend.week_start == week_start,
            DiseaseWeeklyTrend.branch_id == self.branch_id,
        ).delete()
        self.db.flush()

        # Current week SSDO entries
        q = self.db.query(SSDOIndex).filter(
            SSDOIndex.record_type == "test_result",
            SSDOIndex.temporal_position.between(start_dt, end_dt),
            SSDOIndex.disease_tags.isnot(None),
        )
        if self.branch_id:
            q = q.filter(SSDOIndex.branch_id == self.branch_id)
        current_entries = q.all()

        # Previous week for trend comparison
        q_prev = self.db.query(SSDOIndex).filter(
            SSDOIndex.record_type == "test_result",
            SSDOIndex.temporal_position.between(prev_start_dt, start_dt),
            SSDOIndex.disease_tags.isnot(None),
        )
        if self.branch_id:
            q_prev = q_prev.filter(SSDOIndex.branch_id == self.branch_id)
        prev_entries = q_prev.all()

        # Build current counts
        current_counts: dict[str, dict] = {}
        for e in current_entries:
            if not isinstance(e.disease_tags, list):
                continue
            for tag in e.disease_tags:
                if tag not in current_counts:
                    current_counts[tag] = {
                        "count": 0,
                        "critical": 0,
                        "patients": set(),
                        "category": e.test_category,
                    }
                current_counts[tag]["count"] += 1
                if e.severity_flag == "critical":
                    current_counts[tag]["critical"] += 1
                if e.patient_id:
                    current_counts[tag]["patients"].add(e.patient_id)

        # Build previous counts for trend direction
        prev_counts: dict[str, int] = {}
        for e in prev_entries:
            if not isinstance(e.disease_tags, list):
                continue
            for tag in e.disease_tags:
                prev_counts[tag] = prev_counts.get(tag, 0) + 1

        trends: list[DiseaseWeeklyTrend] = []
        for tag, data in current_counts.items():
            prev = prev_counts.get(tag, 0)
            curr = data["count"]

            if prev == 0 or curr > prev * 1.1:
                direction = "rising"
            elif curr < prev * 0.9:
                direction = "falling"
            else:
                direction = "stable"

            trend = DiseaseWeeklyTrend(
                week_start=week_start,
                week_end=week_end,
                branch_id=self.branch_id,
                disease_tag=tag,
                test_category=data["category"],
                occurrence_count=curr,
                critical_count=data["critical"],
                affected_patient_count=len(data["patients"]),
                trend_direction=direction,
                previous_week_count=prev,
            )
            self.db.add(trend)
            trends.append(trend)

        self.db.commit()
        return trends

    def get_weekly_trends(
        self,
        week_start: Optional[date] = None,
        limit: int = 20,
    ) -> list[DiseaseWeeklyTrend]:
        q = self.db.query(DiseaseWeeklyTrend)
        if self.branch_id:
            q = q.filter(DiseaseWeeklyTrend.branch_id == self.branch_id)
        if week_start:
            q = q.filter(DiseaseWeeklyTrend.week_start == week_start)
        return (
            q.order_by(
                DiseaseWeeklyTrend.week_start.desc(),
                DiseaseWeeklyTrend.occurrence_count.desc()
            )
            .limit(limit)
            .all()
        )