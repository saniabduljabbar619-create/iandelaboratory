# app/services/dashboard_service.py

from sqlalchemy.orm import Session
from sqlalchemy import func, and_
from datetime import datetime, timedelta

from app.core.branch_scope import resolve_branch_scope
from app.models.patient import Patient
from app.models.test_request import TestRequest
from app.models.test_result import TestResult, ResultStatus
from app.models.payment import Payment
from app.models.notification_model import Notification
from app.models.booking import Booking
from app.models.user import User # Vital for branch resolution

class DashboardService:

    def __init__(self, db: Session, current_user, requested_branch_id=None):
        self.db = db
        self.branch_id = resolve_branch_scope(current_user, requested_branch_id)

    def _apply_branch_filter(self, query, model):
        """Standard filter for models that have a direct branch_id column."""
        if self.branch_id and hasattr(model, 'branch_id'):
            return query.filter(model.branch_id == self.branch_id)
        return query

    def get_metrics(self):
        """
        Gathers overall KPIs for the Dashboard cards.
        Updated with the 'Notification Link' logic to fix ₦0.00 debt issue.
        """
        # 1. Total Patients
        total_patients = self._apply_branch_filter(self.db.query(func.count(Patient.id)), Patient).scalar() or 0

        # 2. Pending Requests
        pending_requests = self._apply_branch_filter(
            self.db.query(func.count(TestRequest.id)).filter(TestRequest.status == "pending"), 
            TestRequest
        ).scalar() or 0

        # 3. Results Pending Review
        pending_review = self._apply_branch_filter(
            self.db.query(func.count(TestResult.id)).filter(TestResult.status == ResultStatus.pending_review),
            TestResult
        ).scalar() or 0

        # 4. Total Cash Banked (Realized Revenue)
        total_revenue = self._apply_branch_filter(
            self.db.query(func.sum(Payment.amount)).filter(Payment.status == "completed"),
            Payment
        ).scalar() or 0.0

        # 5. Total Credit Owed (THE DEBT FIX)
        # We match solely on the Notification link as confirmed by your SQL success
        credit_q = self.db.query(func.sum(Booking.total_amount))\
            .join(Notification, Notification.reference_id == Booking.id)\
            .join(User, Booking.approved_by_user_id == User.id)\
            .filter(
                Notification.type == "credit_approved",
                Notification.reference_type == "booking"
            )
        
        if self.branch_id:
            credit_q = credit_q.filter(User.branch_id == self.branch_id)
            
        total_credit = credit_q.scalar() or 0.0

        return {
            "patients": total_patients,
            "pending_requests": pending_requests,
            "pending_review": pending_review,
            "revenue": float(total_revenue),
            "total_credit": float(total_credit),
        }

    def get_today_metrics(self):
        """Gathers metrics for the top 'Today Strip'."""
        today = datetime.utcnow().date()
        tomorrow = today + timedelta(days=1)

        p_today = self._apply_branch_filter(
            self.db.query(func.count(Patient.id)).filter(
                and_(Patient.created_at >= today, Patient.created_at < tomorrow)
            ), Patient
        ).scalar() or 0

        r_today = self._apply_branch_filter(
            self.db.query(func.sum(Payment.amount)).filter(
                and_(Payment.created_at >= today, Payment.created_at < tomorrow, Payment.status == "completed")
            ), Payment
        ).scalar() or 0.0
        
        # Debt Today (Fixed logic)
        debt_today_q = self.db.query(func.sum(Booking.total_amount))\
            .join(Notification, Notification.reference_id == Booking.id)\
            .join(User, Booking.approved_by_user_id == User.id)\
            .filter(
                and_(
                    Notification.created_at >= today,
                    Notification.created_at < tomorrow,
                    Notification.type == "credit_approved"
                )
            )
        
        if self.branch_id:
            debt_today_q = debt_today_q.filter(User.branch_id == self.branch_id)
            
        debt_today = debt_today_q.scalar() or 0.0

        return {
            "patients_today": p_today,
            "requests_today": 0, 
            "revenue_today": float(r_today),
            "debt_today": float(debt_today)
        }

    def get_last_7_days_revenue(self):
        start = datetime.utcnow().date() - timedelta(days=6)
        query = self.db.query(
            func.date(Payment.created_at).label("date"),
            func.sum(Payment.amount).label("daily_sum")
        ).filter(Payment.status == "completed", Payment.created_at >= start)
        
        return self._apply_branch_filter(query, Payment).group_by(func.date(Payment.created_at)).all()

    def get_recent_activity(self, limit=10):
        from app.models.audit_log import AuditLog
        q = self.db.query(AuditLog).order_by(AuditLog.created_at.desc())
        if self.branch_id:
            q = q.filter(AuditLog.branch_id == self.branch_id)
        return q.limit(limit).all()


    def get_referrer_debt_ledger(self, limit=10):
        """
        Populates the 'Approved Referrer Debt Ledger' table.
        Groups debt by referrer name/phone based on approved credit notifications.
        """
        query = self.db.query(
            Booking.referrer_name,
            Booking.referrer_phone,
            func.sum(Booking.total_amount).label("total_debt"),
            func.count(Booking.id).label("booking_count"),
            func.max(Notification.created_at).label("last_approved")
        ).join(Notification, Notification.reference_id == Booking.id)\
         .join(User, Booking.approved_by_user_id == User.id)\
         .filter(
            Notification.type == "credit_approved",
            Notification.reference_type == "booking"
        )

        # Apply branch scoping
        if self.branch_id:
            query = query.filter(User.branch_id == self.branch_id)

        # Group by referrer to aggregate the debt
        return query.group_by(Booking.referrer_name, Booking.referrer_phone)\
                    .order_by(func.sum(Booking.total_amount).desc())\
                    .limit(limit)\
                    .all()