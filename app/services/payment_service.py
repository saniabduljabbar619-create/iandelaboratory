# -*- coding: utf-8 -*-
# app/services/payment_service.py

from __future__ import annotations

from fastapi import HTTPException
from sqlalchemy.orm import Session
from sqlalchemy import func
from app.models.payment import Payment
from app.models.test_request import TestRequest
from app.schemas.payment import PaymentCreate
from app.core.branch_scope import resolve_branch_scope
from app.models.patient import Patient

from datetime import datetime
from app.models.user import User
from app.models.payment_proof_model import PaymentProof
from app.models.booking import Booking
from app.services.notification_service import NotificationService


def _csv_from_ids(ids: list[int]) -> str:
    ids2 = []
    for x in ids or []:
        try:
            n = int(x)
            if n > 0:
                ids2.append(n)
        except Exception:
            continue
    return ",".join(str(n) for n in ids2)


def _ids_from_csv(s: str | None) -> list[int]:
    if not s:
        return []
    out = []
    for part in str(s).split(","):
        part = part.strip()
        if not part:
            continue
        try:
            n = int(part)
            if n > 0:
                out.append(n)
        except Exception:
            continue
    return out


class PaymentService:
    def __init__(self, db: Session, current_user, requested_branch_id: int | None = None):
        self.db = db
        self.current_user = current_user
        self.branch_id = resolve_branch_scope(current_user, requested_branch_id)

    def list(self, patient_id: int, limit: int = 200) -> list[Payment]:
        q = self.db.query(Payment).filter(Payment.patient_id == int(patient_id))

        if self.branch_id:
            q = q.filter(Payment.branch_id == self.branch_id)

        return q.order_by(Payment.created_at.desc()).limit(limit).all()

    def create(self, payload: PaymentCreate) -> Payment:
        request_ids = [int(x) for x in (payload.request_ids or []) if int(x) > 0]

        try:
            # Validate patient branch
            patient_query = self.db.query(Patient).filter(
                Patient.id == int(payload.patient_id)
            )

            if self.branch_id:
                patient_query = patient_query.filter(Patient.branch_id == self.branch_id)

            patient = patient_query.first()

            if not patient:
                raise HTTPException(status_code=404, detail="Patient not found")

            # Create payment bound to patient branch
            p = Payment(
                patient_id=int(payload.patient_id),
                branch_id=patient.branch_id,
                amount=float(payload.amount),
                method=str(payload.method),
                status="completed",
                request_ids_csv=_csv_from_ids(request_ids) or None,
                notes=(payload.notes or None),
                created_by_id=self.current_user.id  # <--- CAPTURE THE CASHIER ID
            )

            self.db.add(p)
            self.db.flush()

            if request_ids:
                req_query = self.db.query(TestRequest).filter(
                    TestRequest.id.in_(request_ids)
                )

                if self.branch_id:
                    req_query = req_query.filter(TestRequest.branch_id == self.branch_id)

                reqs = req_query.all()

                found_ids = {r.id for r in reqs}
                missing = [rid for rid in request_ids if rid not in found_ids]
                if missing:
                    raise HTTPException(
                        status_code=404,
                        detail=f"Test request(s) not found: {missing}",
                    )

                # Ensure same patient
                bad = [r.id for r in reqs if int(r.patient_id) != int(payload.patient_id)]
                if bad:
                    raise HTTPException(
                        status_code=400,
                        detail=f"Request(s) not for this patient: {bad}",
                    )

                # Ensure pending
                not_pending = [
                    r.id for r in reqs
                    if (r.status or "").strip().lower() != "pending"
                ]
                if not_pending:
                    raise HTTPException(
                        status_code=400,
                        detail=f"Request(s) not payable (must be pending): {not_pending}",
                    )

                for r in reqs:
                    r.status = "paid"

            self.db.commit()
            self.db.refresh(p)
            return p

        except HTTPException:
            self.db.rollback()
            raise
        except Exception as e:
            self.db.rollback()
            raise HTTPException(status_code=500, detail=str(e))

    @staticmethod
    def parse_request_ids(payment: Payment) -> list[int]:
        return _ids_from_csv(payment.request_ids_csv)
    

    @staticmethod
    def approve_payment(db: Session, proof_id: int, admin_id: int):

        proof = db.query(PaymentProof).filter(
            PaymentProof.id == proof_id
        ).first()

        if not proof:
            raise HTTPException(status_code=404, detail="Payment proof not found")

        if proof.status == "approved":
            raise HTTPException(status_code=400, detail="Payment already approved")

        booking = db.query(Booking).filter(
            Booking.id == proof.booking_id
        ).first()

        if not booking:
            raise HTTPException(status_code=404, detail="Booking not found")

        if booking.status != "awaiting_verification":
            raise HTTPException(
                status_code=400,
                detail="Booking is not awaiting payment verification"
            )

        # 🔒 IDEMPOTENCY CHECK (CRITICAL)
        existing_payment = db.query(Payment).filter(
            Payment.notes == f"BOOKING:{booking.id}"
        ).first()

        if existing_payment:
            raise HTTPException(
                status_code=400,
                detail="Payment already recorded for this booking"
            )

        # ✅ CREATE PAYMENT RECORD
        admin_user = db.query(User).filter(User.id == admin_id).first()
        if not admin_user:
            raise HTTPException(status_code=404, detail="Admin user not found")

        # 🔥 BRANCH RESOLUTION LOGIC
        if admin_user.role == "super_admin":
            # Super admin operates globally → assign default operational branch
            branch_id = 1  # ⚠️ your active branch (Head Office or main branch)
        else:
            if not admin_user.branch_id:
                raise HTTPException(status_code=400, detail="Admin has no branch assigned")
            branch_id = admin_user.branch_id

        payment = Payment(
            patient_id=None,
            amount=float(booking.total_amount),
            method="Transfer",
            status="completed",
            notes=f"BOOKING:{booking.id}",
            branch_id=branch_id,
            created_by_id=admin_id  # <--- CAPTURE THE VERIFYING ADMIN ID
        )

        db.add(payment)

        # ✅ UPDATE PROOF
        proof.status = "approved"
        proof.verified_by = admin_id
        proof.verified_at = datetime.utcnow()

        # ✅ UPDATE BOOKING
        booking.status = "payment_verified"
        booking.approved_by_user_id = admin_id
        booking.approved_at = datetime.utcnow()

        db.commit()

        # ✅ NOTIFICATION (unchanged)
        NotificationService.create(
            db=db,
            type="payment_verified",
            title="Payment Verified",
            message=f"Booking {booking.booking_code} payment has been verified.",
            reference_type="booking",
            reference_id=booking.id
        )

        return proof

    @staticmethod
    def reject_payment(db: Session, proof_id: int, admin_id: int, note: str):

        proof = db.query(PaymentProof).filter(
            PaymentProof.id == proof_id
        ).first()

        if not proof:
            raise HTTPException(status_code=404, detail="Payment proof not found")

        if proof.status == "approved":
            raise HTTPException(
                status_code=400,
                detail="Cannot reject an already approved payment"
            )

        booking = db.query(Booking).filter(
            Booking.id == proof.booking_id
        ).first()

        if not booking:
            raise HTTPException(status_code=404, detail="Booking not found")

        if booking.status != "awaiting_verification":
            raise HTTPException(
                status_code=400,
                detail="Booking is not awaiting payment verification"
            )

        proof.status = "rejected"
        proof.note = note
        proof.verified_by = admin_id
        proof.verified_at = datetime.utcnow()

        booking.status = "payment_rejected"

        db.commit()

        return proof





    def reconcile(
            self, 
            start_date: datetime | None = None, 
            end_date: datetime | None = None, 
            method: str | None = None
        ) -> list[Payment]:
            """
            Retrieves payments for administrative reconciliation.
            Filters by branch_id (auto-resolved), date range, and payment method.
            """
            query = self.db.query(Payment)
    
            # 1. Apply Branch Scope (Determined during __init__)
            if self.branch_id:
                query = query.filter(Payment.branch_id == self.branch_id)
    
            # 2. Date Range Filtering
            if start_date:
                query = query.filter(Payment.created_at >= start_date)
            
            if end_date:
                # Ensure we include the entire end day if it's a date-only object
                query = query.filter(Payment.created_at <= end_date)
    
            # 3. Method Filtering (Cash vs Transfer vs POS)
            if method:
                query = query.filter(Payment.method == method)
    
            return query.order_by(Payment.created_at.desc()).all()

    def reconcile_summary(self, start_date=None, end_date=None):
        query = self.db.query(
            Payment.method, 
            func.sum(Payment.amount).label("total_amount")
        )
    
        if self.branch_id:
            query = query.filter(Payment.branch_id == self.branch_id)
    
        if start_date:
            query = query.filter(Payment.created_at >= start_date)
        if end_date:
            query = query.filter(Payment.created_at <= end_date)
    
        results = query.group_by(Payment.method).all()
    
        summary = {row.method: float(row.total_amount) for row in results}
        summary["total"] = sum(summary.values())
        return summary



    def cashier_today_summary(self) -> dict:
        """
        Returns TODAY's snapshot for the logged-in cashier only
        (isolation model): their revenue, tests billed, and pending count.
        """
        from datetime import datetime, time
        from app.models.test_request import TestRequest

        today = datetime.now().date()
        start = datetime.combine(today, time.min)
        end = datetime.combine(today, time.max)

        uid = self.current_user.id

        # Revenue today — this cashier's payments only
        pay_q = self.db.query(func.coalesce(func.sum(Payment.amount), 0)).filter(
            Payment.created_by_id == uid,
            Payment.created_at >= start,
            Payment.created_at <= end,
        )
        if self.branch_id:
            pay_q = pay_q.filter(Payment.branch_id == self.branch_id)
        revenue_today = float(pay_q.scalar() or 0)

        # Tests billed today — count of request_ids across this cashier's payments today
        pay_rows = self.db.query(Payment).filter(
            Payment.created_by_id == uid,
            Payment.created_at >= start,
            Payment.created_at <= end,
        ).all()
        tests_billed = sum(len(self.parse_request_ids(p)) for p in pay_rows)

        # Pending bills — count of pending requests in this branch
        pend_q = self.db.query(func.count(TestRequest.id)).filter(
            TestRequest.status == "pending",
        )
        if self.branch_id:
            pend_q = pend_q.filter(TestRequest.branch_id == self.branch_id)
        pending_count = int(pend_q.scalar() or 0)

        return {
            "revenue_today": revenue_today,
            "tests_billed_today": tests_billed,
            "pending_bills": pending_count,
        }
        
        
    def cashier_period_report(self, start_date=None, end_date=None) -> dict:
        """
        Financial report for the logged-in cashier over a period (isolation).
        Returns totals, per-method breakdown, top tests, and daily revenue.
        """
        from datetime import datetime, time, date as _date
        from collections import defaultdict
        from app.models.test_type import TestType

        uid = self.current_user.id

        q = self.db.query(Payment).filter(Payment.created_by_id == uid)
        if self.branch_id:
            q = q.filter(Payment.branch_id == self.branch_id)
        if start_date:
            q = q.filter(Payment.created_at >= start_date)
        if end_date:
            q = q.filter(Payment.created_at <= end_date)
        payments = q.order_by(Payment.created_at.desc()).all()

        total_revenue = sum(float(p.amount or 0) for p in payments)
        method_breakdown = defaultdict(float)
        daily = defaultdict(float)
        all_request_ids: list[int] = []

        for p in payments:
            method_breakdown[p.method or "Cash"] += float(p.amount or 0)
            if p.created_at:
                daily[p.created_at.date().isoformat()] += float(p.amount or 0)
            all_request_ids.extend(self.parse_request_ids(p))

        tests_billed = len(all_request_ids)

        # Top tests by frequency among paid requests
        top_tests = []
        if all_request_ids:
            from app.models.test_request import TestRequest
            reqs = self.db.query(TestRequest).filter(TestRequest.id.in_(all_request_ids)).all()
            type_counts = defaultdict(int)
            for r in reqs:
                type_counts[r.test_type_id] += 1
            # resolve names + prices
            type_ids = list(type_counts.keys())
            types = self.db.query(TestType).filter(TestType.id.in_(type_ids)).all() if type_ids else []
            tmap = {t.id: t for t in types}
            for tid, cnt in sorted(type_counts.items(), key=lambda x: x[1], reverse=True)[:8]:
                tt = tmap.get(tid)
                top_tests.append({
                    "name": tt.name if tt else f"Test #{tid}",
                    "count": cnt,
                    "revenue": float(tt.price) * cnt if tt else 0,
                })

        return {
            "total_revenue": total_revenue,
            "tests_billed": tests_billed,
            "payment_count": len(payments),
            "method_breakdown": dict(method_breakdown),
            "top_tests": top_tests,
            "daily_revenue": dict(sorted(daily.items())),
        }