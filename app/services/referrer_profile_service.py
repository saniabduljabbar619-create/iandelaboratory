# -*- coding: utf-8 -*-
# app/services/referrer_profile_service.py
"""
Smart Referrer Profile Service — v2.0.
Unifies both patient flows (Booking and ReferralBatch),
integrates SSDO disease intelligence, and enables
per-patient result downloads.
"""
from __future__ import annotations

import os
import shutil
from pathlib import Path
from typing import Optional

from fastapi import HTTPException, UploadFile
from sqlalchemy.orm import Session
from sqlalchemy import or_

from app.models.referrer import Referrer
from app.models.booking import Booking
from app.models.booking_item import BookingItem
from app.models.referral_batch import ReferralBatch
from app.models.referral_bridge import ReferralBridge
from app.models.referral_ledger import ReferralLedger
from app.models.test_request import TestRequest
from app.models.test_result import TestResult
from app.models.patient import Patient
from app.services.ssdo.query_engine import SSDOQueryEngine
from app.services.result_pdf_service import generate_result_pdf


AVATAR_DIR = Path("uploads/referrers")
ALLOWED_IMAGE_TYPES = {"image/jpeg", "image/png", "image/webp"}


class ReferrerProfileService:

    def __init__(self, db: Session):
        self.db = db
        self.ssdo = SSDOQueryEngine(db)

    # --------------------------------------------------
    # PROFILE
    # --------------------------------------------------

    def get_referrer(self, referrer_id: int) -> Referrer:
        ref = self.db.query(Referrer).filter(
            Referrer.id == referrer_id
        ).first()
        if not ref:
            raise HTTPException(status_code=404, detail="Referrer not found.")
        return ref

    def get_profile(self, referrer_id: int) -> dict:
        ref = self.get_referrer(referrer_id)
        avatar_url = f"/uploads/referrers/{referrer_id}.jpg" if ref.avatar_path else None

        # Quick stats
        total_patients = self._count_unique_patients(referrer_id)
        total_batches = self.db.query(ReferralBatch).filter(
            ReferralBatch.referrer_id == referrer_id
        ).count()

        financial = self._get_financial_summary(referrer_id)

        return {
            "id": ref.id,
            "name": ref.name,
            "email": ref.email,
            "phone": ref.phone,
            "organization_type": ref.organization_type,
            "address": ref.address,
            "contact_person": ref.contact_person,
            "license_no": ref.license_no,
            "discount_percent": float(ref.discount_percent or 0),
            "notes": ref.notes,
            "avatar_url": avatar_url,
            "credit_limit": float(ref.credit_limit or 0),
            "is_active": ref.is_active,
            "created_at": ref.created_at.isoformat() if ref.created_at else None,
            "stats": {
                "total_patients": total_patients,
                "total_batches": total_batches,
            },
            "financial": financial,
        }

    def update_profile(self, referrer_id: int, data: dict) -> dict:
        ref = self.get_referrer(referrer_id)
        allowed = {
            "name", "email", "phone", "organization_type",
            "address", "contact_person", "license_no",
            "discount_percent", "notes", "credit_limit",
        }
        for key, value in data.items():
            if key in allowed and value is not None:
                setattr(ref, key, value)
        self.db.commit()
        self.db.refresh(ref)
        return self.get_profile(referrer_id)

    # --------------------------------------------------
    # AVATAR UPLOAD
    # --------------------------------------------------

    def upload_avatar(self, referrer_id: int, file: UploadFile) -> dict:
        ref = self.get_referrer(referrer_id)

        if file.content_type not in ALLOWED_IMAGE_TYPES:
            raise HTTPException(
                status_code=400,
                detail=f"Invalid file type. Allowed: JPEG, PNG, WebP."
            )

        AVATAR_DIR.mkdir(parents=True, exist_ok=True)
        dest = AVATAR_DIR / f"{referrer_id}.jpg"

        with dest.open("wb") as f:
            shutil.copyfileobj(file.file, f)

        ref.avatar_path = str(dest)
        self.db.commit()

        return {
            "message": "Avatar uploaded successfully.",
            "avatar_url": f"/uploads/referrers/{referrer_id}.jpg",
        }

    # --------------------------------------------------
    # UNIFIED PATIENT LIST
    # Pulls from BOTH the Booking flow and ReferralBatch flow
    # --------------------------------------------------

    def get_referred_patients(
        self,
        referrer_id: int,
        limit: int = 50,
        offset: int = 0,
    ) -> dict:
        """
        Unified patient list across both referral flows.
        Flow A: Referrer → Booking → BookingItem → patient_id
        Flow B: Referrer → ReferralBatch → ReferralBridge → TestRequest → patient_id
        """
        patient_ids: set[int] = set()

        # Flow A — Booking flow
        booking_items = (
            self.db.query(BookingItem.patient_id)
            .join(Booking, BookingItem.booking_id == Booking.id)
            .filter(
                Booking.referrer_id == referrer_id,
                BookingItem.patient_id.isnot(None),
            )
            .all()
        )
        patient_ids.update(row[0] for row in booking_items)

        # Flow B — ReferralBatch flow
        bridge_patients = (
            self.db.query(TestRequest.patient_id)
            .join(ReferralBridge, ReferralBridge.test_request_id == TestRequest.id)
            .join(ReferralBatch, ReferralBatch.batch_uid == ReferralBridge.batch_uid)
            .filter(
                ReferralBatch.referrer_id == referrer_id,
                TestRequest.patient_id.isnot(None),
            )
            .all()
        )
        patient_ids.update(row[0] for row in bridge_patients)
        
        # Flow C — Direct link (cashier set patient.referrer_id at registration)
        direct_patients = (
            self.db.query(Patient.id)
            .filter(Patient.referrer_id == referrer_id)
            .all()
        )
        patient_ids.update(row[0] for row in direct_patients)

        if not patient_ids:
            return {"patients": [], "total": 0}

        all_ids = sorted(patient_ids)
        paginated_ids = all_ids[offset: offset + limit]

        patients = (
            self.db.query(Patient)
            .filter(Patient.id.in_(paginated_ids))
            .order_by(Patient.full_name)
            .all()
        )

        result = []
        for p in patients:
            # Get SSDO disease history for this patient
            disease_history = self.ssdo.get_patient_disease_history(p.id)

            # Get their test results
            results = (
                self.db.query(TestResult)
                .filter(TestResult.patient_id == p.id)
                .order_by(TestResult.created_at.desc())
                .limit(10)
                .all()
            )

            result.append({
                "patient_id": p.id,
                "patient_no": p.patient_no,
                "full_name": p.full_name,
                "phone": p.phone,
                "gender": p.gender,
                "disease_history": disease_history,
                "results": [
                    {
                        "result_id": r.id,
                        "sync_id": r.sync_id,
                        "status": r.status.value if hasattr(r.status, "value") else str(r.status),
                        "created_at": r.created_at.isoformat() if r.created_at else None,
                        "download_url": f"/api/referrer/{referrer_id}/patients/{p.id}/results/{r.id}/download",
                        "sas_assisted": bool(r.sas_predictions),
                    }
                    for r in results
                ],
            })

        return {"patients": result, "total": len(all_ids)}

    # --------------------------------------------------
    # RESULT DOWNLOAD
    # --------------------------------------------------

    def download_patient_result(
        self,
        referrer_id: int,
        patient_id: int,
        result_id: int,
    ) -> Path:
        """
        Validates the referrer has access to this patient,
        then generates and returns the PDF path.
        """
        # Verify this patient belongs to this referrer
        patient_ids = self.get_referred_patients(referrer_id, limit=9999)
        referred_ids = {p["patient_id"] for p in patient_ids["patients"]}

        if patient_id not in referred_ids:
            raise HTTPException(
                status_code=403,
                detail="This patient was not referred by this referrer."
            )

        result = self.db.query(TestResult).filter(
            TestResult.id == result_id,
            TestResult.patient_id == patient_id,
        ).first()

        if not result:
            raise HTTPException(status_code=404, detail="Result not found.")

        from app.models.test_result import ResultStatus
        if result.status not in [ResultStatus.released, ResultStatus.draft]:
            raise HTTPException(
                status_code=400,
                detail="Result is not available for download yet."
            )

        return generate_result_pdf(result, source="portal")

    # --------------------------------------------------
    # BATCH HISTORY
    # --------------------------------------------------

    def get_batch_history(self, referrer_id: int, limit: int = 20) -> list[dict]:
        batches = (
            self.db.query(ReferralBatch)
            .filter(ReferralBatch.referrer_id == referrer_id)
            .order_by(ReferralBatch.created_at.desc())
            .limit(limit)
            .all()
        )

        result = []
        for b in batches:
            # Count patients in this batch
            patient_count = (
                self.db.query(ReferralBridge)
                .filter(ReferralBridge.batch_uid == b.batch_uid)
                .count()
            )

            # Get ledger for this batch
            ledger = (
                self.db.query(ReferralLedger)
                .filter(ReferralLedger.batch_uid == b.batch_uid)
                .first()
            )

            result.append({
                "batch_uid": b.batch_uid,
                "status": b.status,
                "date_received": b.date_received.isoformat() if b.date_received else None,
                "date_due": b.date_due.isoformat() if b.date_due else None,
                "courier_info": b.courier_info,
                "patient_count": patient_count,
                "financial": {
                    "gross_total": float(ledger.gross_total) if ledger else 0,
                    "discount_percent": float(ledger.discount_percent) if ledger else 0,
                    "net_payable": float(ledger.net_payable) if ledger else 0,
                    "is_settled": ledger.is_settled if ledger else False,
                } if ledger else None,
                "created_at": b.created_at.isoformat() if b.created_at else None,
            })

        return result

    # --------------------------------------------------
    # SSDO INSIGHTS — disease patterns across all referred patients
    # --------------------------------------------------

    def get_ssdo_insights(self, referrer_id: int) -> dict:
        """
        Aggregates SSDO disease intelligence across ALL
        patients referred by this referrer.
        Gives the referring clinic a population-level view.
        """
        patient_ids = self.get_referred_patients(referrer_id, limit=9999)
        all_patient_ids = [p["patient_id"] for p in patient_ids["patients"]]

        if not all_patient_ids:
            return {
                "total_patients": 0,
                "disease_frequency": [],
                "severity_distribution": {},
                "category_distribution": [],
            }

        # Aggregate disease tags across all patients
        from app.models.ssdo_index import SSDOIndex
        entries = (
            self.db.query(SSDOIndex)
            .filter(
                SSDOIndex.patient_id.in_(all_patient_ids),
                SSDOIndex.record_type == "test_result",
            )
            .all()
        )

        tag_counts: dict[str, int] = {}
        severity_counts: dict[str, int] = {}
        category_counts: dict[str, int] = {}

        for e in entries:
            if isinstance(e.disease_tags, list):
                for tag in e.disease_tags:
                    tag_counts[tag] = tag_counts.get(tag, 0) + 1

            sev = e.severity_flag or "unknown"
            severity_counts[sev] = severity_counts.get(sev, 0) + 1

            cat = e.test_category or "Unknown"
            category_counts[cat] = category_counts.get(cat, 0) + 1

        return {
            "total_patients": len(all_patient_ids),
            "total_results_indexed": len(entries),
            "disease_frequency": [
                {"disease_tag": tag, "count": cnt}
                for tag, cnt in sorted(tag_counts.items(), key=lambda x: x[1], reverse=True)[:15]
            ],
            "severity_distribution": severity_counts,
            "category_distribution": [
                {"category": cat, "count": cnt}
                for cat, cnt in sorted(category_counts.items(), key=lambda x: x[1], reverse=True)
            ],
        }

    # --------------------------------------------------
    # FINANCIAL SUMMARY
    # --------------------------------------------------

    def _get_financial_summary(self, referrer_id: int) -> dict:
        from sqlalchemy import func as sqlfunc

        # From ledgers
        ledger_totals = (
            self.db.query(
                sqlfunc.coalesce(sqlfunc.sum(ReferralLedger.gross_total), 0).label("gross"),
                sqlfunc.coalesce(sqlfunc.sum(ReferralLedger.net_payable), 0).label("net"),
            )
            .filter(ReferralLedger.referrer_id == referrer_id)
            .first()
        )

        outstanding = (
            self.db.query(
                sqlfunc.coalesce(sqlfunc.sum(ReferralLedger.net_payable), 0)
            )
            .filter(
                ReferralLedger.referrer_id == referrer_id,
                ReferralLedger.is_settled == False,
            )
            .scalar()
        )

        settled = (
            self.db.query(
                sqlfunc.coalesce(sqlfunc.sum(ReferralLedger.net_payable), 0)
            )
            .filter(
                ReferralLedger.referrer_id == referrer_id,
                ReferralLedger.is_settled == True,
            )
            .scalar()
        )

        return {
            "gross_total": float(ledger_totals.gross or 0),
            "net_total": float(ledger_totals.net or 0),
            "outstanding_balance": float(outstanding or 0),
            "total_settled": float(settled or 0),
        }

    def _count_unique_patients(self, referrer_id: int) -> int:
        patient_ids: set[int] = set()

        rows_a = (
            self.db.query(BookingItem.patient_id)
            .join(Booking, BookingItem.booking_id == Booking.id)
            .filter(
                Booking.referrer_id == referrer_id,
                BookingItem.patient_id.isnot(None),
            )
            .all()
        )
        patient_ids.update(r[0] for r in rows_a)

        rows_b = (
            self.db.query(TestRequest.patient_id)
            .join(ReferralBridge, ReferralBridge.test_request_id == TestRequest.id)
            .join(ReferralBatch, ReferralBatch.batch_uid == ReferralBridge.batch_uid)
            .filter(
                ReferralBatch.referrer_id == referrer_id,
                TestRequest.patient_id.isnot(None),
            )
            .all()
        )
        patient_ids.update(r[0] for r in rows_b)
        
        
        rows_c = (
            self.db.query(Patient.id)
            .filter(Patient.referrer_id == referrer_id)
            .all()
        )
        patient_ids.update(r[0] for r in rows_c)

        return len(patient_ids)