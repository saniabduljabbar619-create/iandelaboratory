# -*- coding: utf-8 -*-
# app/services/ssdo/query_engine.py
"""
SSDO Query Engine — structured retrieval for SAS consumption.
All SAS analysis starts here. Never queries raw tables directly —
always goes through the SSDO index.
"""
from __future__ import annotations

from datetime import datetime
from typing import Optional

from sqlalchemy.orm import Session
from sqlalchemy import desc, func

from app.models.ssdo_index import SSDOIndex


class SSDOQueryEngine:

    def __init__(self, db: Session):
        self.db = db

    # --------------------------------------------------
    # PATIENT TIMELINE
    # --------------------------------------------------

    def get_patient_timeline(
        self,
        patient_id: int,
        limit: int = 50
    ) -> list[dict]:
        """
        Returns the complete chronological record timeline for a patient.
        Used by SAS patient_analyzer to build the clinical profile.
        """
        entries = (
            self.db.query(SSDOIndex)
            .filter(SSDOIndex.patient_id == patient_id)
            .order_by(desc(SSDOIndex.temporal_position))
            .limit(limit)
            .all()
        )

        return [self._serialize(e) for e in entries]

    def get_patient_results_by_category(
        self,
        patient_id: int,
        category: str,
        limit: int = 20
    ) -> list[dict]:
        """
        Returns all indexed results for a patient in a specific category.
        e.g. all Haematology results for patient X.
        """
        entries = (
            self.db.query(SSDOIndex)
            .filter(
                SSDOIndex.patient_id == patient_id,
                SSDOIndex.record_type == "test_result",
                SSDOIndex.test_category == category,
            )
            .order_by(desc(SSDOIndex.temporal_position))
            .limit(limit)
            .all()
        )
        return [self._serialize(e) for e in entries]

    def get_patient_disease_history(self, patient_id: int) -> list[str]:
        """
        Returns all unique disease tags ever recorded for this patient.
        Used by SAS to build disease history summary.
        """
        entries = (
            self.db.query(SSDOIndex.disease_tags)
            .filter(
                SSDOIndex.patient_id == patient_id,
                SSDOIndex.disease_tags.isnot(None),
            )
            .all()
        )

        all_tags: set[str] = set()
        for (tags,) in entries:
            if isinstance(tags, list):
                all_tags.update(tags)

        return sorted(all_tags)

    def get_patient_critical_history(self, patient_id: int) -> list[dict]:
        """Returns all critical severity records for this patient."""
        entries = (
            self.db.query(SSDOIndex)
            .filter(
                SSDOIndex.patient_id == patient_id,
                SSDOIndex.severity_flag == "critical",
            )
            .order_by(desc(SSDOIndex.temporal_position))
            .all()
        )
        return [self._serialize(e) for e in entries]

    # --------------------------------------------------
    # BRANCH / LAB-WIDE QUERIES
    # --------------------------------------------------

    def get_unprocessed_records(
        self,
        branch_id: Optional[int] = None,
        limit: int = 100
    ) -> list[SSDOIndex]:
        """Returns records not yet processed by SAS."""
        q = self.db.query(SSDOIndex).filter(
            SSDOIndex.ai_processed == False
        )
        if branch_id:
            q = q.filter(SSDOIndex.branch_id == branch_id)
        return q.limit(limit).all()

    def get_disease_frequency(
        self,
        branch_id: Optional[int] = None,
        since: Optional[datetime] = None,
        limit: int = 20
    ) -> list[dict]:
        """
        Returns disease tags ordered by frequency.
        Powers the weekly trend analysis and admin dashboard.
        """
        q = (
            self.db.query(SSDOIndex)
            .filter(SSDOIndex.disease_tags.isnot(None))
        )
        if branch_id:
            q = q.filter(SSDOIndex.branch_id == branch_id)
        if since:
            q = q.filter(SSDOIndex.temporal_position >= since)

        entries = q.all()

        tag_counts: dict[str, int] = {}
        for entry in entries:
            if isinstance(entry.disease_tags, list):
                for tag in entry.disease_tags:
                    tag_counts[tag] = tag_counts.get(tag, 0) + 1

        sorted_tags = sorted(
            tag_counts.items(), key=lambda x: x[1], reverse=True
        )

        return [
            {"disease_tag": tag, "count": count}
            for tag, count in sorted_tags[:limit]
        ]

    def get_severity_summary(
        self,
        branch_id: Optional[int] = None,
        since: Optional[datetime] = None
    ) -> dict:
        """Returns count of records per severity level."""
        q = self.db.query(SSDOIndex).filter(
            SSDOIndex.record_type == "test_result"
        )
        if branch_id:
            q = q.filter(SSDOIndex.branch_id == branch_id)
        if since:
            q = q.filter(SSDOIndex.temporal_position >= since)

        entries = q.all()

        summary = {
            "normal": 0,
            "borderline": 0,
            "abnormal": 0,
            "critical": 0,
            "unknown": 0,
        }
        for e in entries:
            flag = e.severity_flag or "unknown"
            if flag in summary:
                summary[flag] += 1
            else:
                summary["unknown"] += 1

        return summary

    def get_category_distribution(
        self,
        branch_id: Optional[int] = None,
        since: Optional[datetime] = None
    ) -> list[dict]:
        """Returns test count per clinical category."""
        q = self.db.query(SSDOIndex).filter(
            SSDOIndex.record_type == "test_result",
            SSDOIndex.test_category.isnot(None),
        )
        if branch_id:
            q = q.filter(SSDOIndex.branch_id == branch_id)
        if since:
            q = q.filter(SSDOIndex.temporal_position >= since)

        entries = q.all()
        counts: dict[str, int] = {}
        for e in entries:
            cat = e.test_category or "Unknown"
            counts[cat] = counts.get(cat, 0) + 1

        return [
            {"category": cat, "count": cnt}
            for cat, cnt in sorted(counts.items(), key=lambda x: x[1], reverse=True)
        ]

    # --------------------------------------------------
    # SERIALIZER
    # --------------------------------------------------

    def _serialize(self, entry: SSDOIndex) -> dict:
        return {
            "id": entry.id,
            "record_type": entry.record_type,
            "record_id": entry.record_id,
            "patient_id": entry.patient_id,
            "test_category": entry.test_category,
            "disease_tags": entry.disease_tags or [],
            "severity_flag": entry.severity_flag,
            "temporal_position": entry.temporal_position.isoformat()
                if entry.temporal_position else None,
            "portal_visible": entry.portal_visible,
            "ai_processed": entry.ai_processed,
            "ai_summary": entry.ai_summary or {},
            "branch_id": entry.branch_id,
            "indexed_at": entry.indexed_at.isoformat()
                if entry.indexed_at else None,
        }