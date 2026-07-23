# -*- coding: utf-8 -*-
# app/services/sas/announcer.py
"""
SAS Voice Announcer — backend side.
Generates VoiceAnnouncement records that the PySide6 desktop
polls for and speaks aloud via pyttsx3.

v2.0 scope: output only.
v3.0 will add microphone input and conversation.
"""
from __future__ import annotations

from datetime import datetime
from typing import Optional

from sqlalchemy.orm import Session

from app.models.voice_announcement import VoiceAnnouncement
from app.models.test_request import TestRequest
from app.models.test_result import TestResult
from app.models.patient import Patient
from app.models.test_type import TestType


class AnnouncerService:

    def __init__(self, db: Session, branch_id: Optional[int] = None):
        self.db = db
        self.branch_id = branch_id

    # --------------------------------------------------
    # ANNOUNCEMENT GENERATORS
    # --------------------------------------------------

    def announce_new_request(self, request_id: int) -> VoiceAnnouncement:
        """
        Fires when a new test request arrives.
        SAS reads it aloud so lab staff know without looking at the screen.
        """
        request = self.db.query(TestRequest).filter(
            TestRequest.id == request_id
        ).first()

        if not request:
            return self._create(
                type="new_request",
                title="New Test Request",
                voice_text="A new test request has arrived and is awaiting processing.",
                priority="normal",
                reference_type="test_request",
                reference_id=request_id,
            )

        patient = self.db.query(Patient).filter(
            Patient.id == request.patient_id
        ).first()

        test_type = self.db.query(TestType).filter(
            TestType.id == request.test_type_id
        ).first()

        patient_name = patient.full_name if patient else "Unknown Patient"
        test_name = test_type.name if test_type else "Unknown Test"
        request_no = getattr(request, "request_no", f"#{request_id}")

        voice_text = (
            f"New test request received. "
            f"{test_name} for {patient_name}. "
            f"Request number {request_no}. "
            f"Please attend to this request."
        )

        return self._create(
            type="new_request",
            title=f"New Request: {test_name}",
            voice_text=voice_text,
            priority="normal",
            reference_type="test_request",
            reference_id=request_id,
        )

    def announce_critical_result(self, result_id: int) -> VoiceAnnouncement:
        """
        Fires when SSDO classifies a result as critical severity.
        Highest priority — spoken immediately on the workstation.
        """
        result = self.db.query(TestResult).filter(
            TestResult.id == result_id
        ).first()

        if not result:
            return self._create(
                type="critical_result",
                title="Critical Result Alert",
                voice_text="Attention. A critical laboratory result requires immediate review.",
                priority="urgent",
                reference_type="test_result",
                reference_id=result_id,
            )

        patient = self.db.query(Patient).filter(
            Patient.id == result.patient_id
        ).first()
        test_type = self.db.query(TestType).filter(
            TestType.id == result.test_type_id
        ).first()

        patient_name = patient.full_name if patient else "a patient"
        test_name = test_type.name if test_type else "a test"

        voice_text = (
            f"Urgent. Critical result detected. "
            f"{test_name} result for {patient_name} contains critical values. "
            f"Immediate review is required before this result is released."
        )

        return self._create(
            type="critical_result",
            title=f"Critical: {test_name}",
            voice_text=voice_text,
            priority="urgent",
            reference_type="test_result",
            reference_id=result_id,
        )

    def announce_abnormal_result(self, result_id: int, disease_tags: list) -> VoiceAnnouncement:
        """
        Fires when SSDO classifies a result as abnormal.
        Normal priority — informs the scientist without interrupting urgently.
        """
        result = self.db.query(TestResult).filter(
            TestResult.id == result_id
        ).first()

        patient = None
        test_type = None
        if result:
            patient = self.db.query(Patient).filter(
                Patient.id == result.patient_id
            ).first()
            test_type = self.db.query(TestType).filter(
                TestType.id == result.test_type_id
            ).first()

        patient_name = patient.full_name if patient else "a patient"
        test_name = test_type.name if test_type else "a test"

        tag_text = ""
        if disease_tags:
            readable = [t.replace("_", " ") for t in disease_tags[:2]]
            tag_text = f" SAS detected possible {' and '.join(readable)}."

        voice_text = (
            f"Abnormal result noted. "
            f"{test_name} for {patient_name} has abnormal values.{tag_text} "
            f"Please review the flagged fields."
        )

        return self._create(
            type="abnormal_result",
            title=f"Abnormal: {test_name}",
            voice_text=voice_text,
            priority="normal",
            reference_type="test_result",
            reference_id=result_id,
        )

    def announce_analysis_summary(self, summary_text: str) -> VoiceAnnouncement:
        """
        Fires when a weekly analytics snapshot is generated.
        Low priority — informational delivery.
        """
        return self._create(
            type="analysis_summary",
            title="Weekly Analysis Summary",
            voice_text=f"SAS weekly analysis is ready. {summary_text}",
            priority="low",
        )

    def announce_sas_suggestion(self, suggestion_text: str, result_id: int) -> VoiceAnnouncement:
        """
        Fires when SAS generates a significant prediction suggestion.
        """
        return self._create(
            type="sas_suggestion",
            title="SAS Suggestion",
            voice_text=f"SAS has a suggestion for the current result. {suggestion_text}",
            priority="normal",
            reference_type="test_result",
            reference_id=result_id,
        )

    def announce_system(self, message: str, priority: str = "normal") -> VoiceAnnouncement:
        """Generic system announcement."""
        return self._create(
            type="system",
            title="System Message",
            voice_text=message,
            priority=priority,
        )

    # --------------------------------------------------
    # QUEUE MANAGEMENT
    # --------------------------------------------------

    def get_pending(self, limit: int = 10) -> list[VoiceAnnouncement]:
        """
        Returns undelivered announcements ordered by priority then time.
        The desktop calls this on its polling interval.
        """
        priority_order = {"urgent": 0, "normal": 1, "low": 2}

        q = self.db.query(VoiceAnnouncement).filter(
            VoiceAnnouncement.is_delivered == False
        )
        if self.branch_id:
            q = q.filter(
                (VoiceAnnouncement.branch_id == self.branch_id) |
                (VoiceAnnouncement.branch_id == None)
            )

        announcements = q.order_by(
            VoiceAnnouncement.created_at.asc()
        ).limit(limit).all()

        # Sort urgent first
        return sorted(
            announcements,
            key=lambda a: (priority_order.get(a.priority, 1), a.created_at)
        )

    def mark_delivered(self, announcement_id: int) -> bool:
        """
        Called by the desktop after pyttsx3 finishes speaking.
        """
        ann = self.db.query(VoiceAnnouncement).filter(
            VoiceAnnouncement.id == announcement_id
        ).first()
        if not ann:
            return False
        ann.is_delivered = True
        ann.delivered_at = datetime.utcnow()
        self.db.commit()
        return True

    def mark_all_delivered(self) -> int:
        """Bulk-mark all pending as delivered — used on workstation shutdown."""
        pending = self.get_pending(limit=100)
        for ann in pending:
            ann.is_delivered = True
            ann.delivered_at = datetime.utcnow()
        self.db.commit()
        return len(pending)

    def clear_old_delivered(self, days: int = 7) -> int:
        """Housekeeping — removes delivered announcements older than N days."""
        from datetime import timedelta
        cutoff = datetime.utcnow() - timedelta(days=days)
        old = self.db.query(VoiceAnnouncement).filter(
            VoiceAnnouncement.is_delivered == True,
            VoiceAnnouncement.delivered_at < cutoff,
        ).all()
        for ann in old:
            self.db.delete(ann)
        self.db.commit()
        return len(old)

    # --------------------------------------------------
    # INTERNAL
    # --------------------------------------------------

    def _create(
        self,
        type: str,
        title: str,
        voice_text: str,
        priority: str = "normal",
        reference_type: Optional[str] = None,
        reference_id: Optional[int] = None,
    ) -> VoiceAnnouncement:
        ann = VoiceAnnouncement(
            type=type,
            title=title,
            voice_text=voice_text,
            priority=priority,
            reference_type=reference_type,
            reference_id=reference_id,
            branch_id=self.branch_id,
            is_delivered=False,
        )
        self.db.add(ann)
        self.db.commit()
        self.db.refresh(ann)
        return ann