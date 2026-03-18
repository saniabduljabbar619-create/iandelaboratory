from sqlalchemy.orm import Session
from sqlalchemy import func
from datetime import datetime

from app.models.test_request import TestRequest
from app.models.payment import Payment
from app.models.booking_item import BookingItem
from app.models.booking import Booking


class ReportService:

    def __init__(self, db: Session, branch_id: int | None = None):
        self.db = db
        self.branch_id = branch_id

    def generate(self, date_from: str, date_to: str):
        d1 = datetime.fromisoformat(date_from)
        d2 = datetime.fromisoformat(date_to)

        # -----------------------------
        # TOTAL TESTS
        # -----------------------------
        q_tests = self.db.query(func.count()).select_from(TestRequest)

        if self.branch_id:
            q_tests = q_tests.filter(TestRequest.branch_id == self.branch_id)

        total_tests = q_tests.filter(
            TestRequest.created_at.between(d1, d2)
        ).scalar() or 0

        # -----------------------------
        # TOTAL REVENUE
        # -----------------------------
        q_rev = self.db.query(func.sum(Payment.amount))

        if self.branch_id:
            q_rev = q_rev.filter(Payment.branch_id == self.branch_id)

        total_revenue = q_rev.filter(
            Payment.created_at.between(d1, d2),
            Payment.status == "completed"
        ).scalar() or 0

        # -----------------------------
        # TOTAL BOOKED VALUE (JOIN)
        # -----------------------------
        q_booked = (
            self.db.query(func.sum(BookingItem.price_snapshot))
            .join(Booking, BookingItem.booking_id == Booking.id)
        )

        total_booked = q_booked.filter(
            Booking.created_at.between(d1, d2)
        ).scalar() or 0

        # -----------------------------
        # PENDING = booked - paid
        # -----------------------------
        pending = float(total_booked) - float(total_revenue)

        if pending < 0:
            pending = 0

        return {
            "total_tests": int(total_tests),
            "total_revenue": float(total_revenue),
            "pending": float(pending),
        }


    # app/services/report_service.py

    def get_patient_clinical_report(self, request_id: int):
        from app.models.patient import Patient
        from app.models.test_result import TestResult
        from app.models.test_request import TestRequest

        try:
            # Perform the join based on YOUR schema: 
            # TestRequest.test_result_id == TestResult.id
            result_data = (
                self.db.query(TestRequest, Patient, TestResult)
                .join(Patient, TestRequest.patient_id == Patient.id)
                .outerjoin(TestResult, TestRequest.test_result_id == TestResult.id) # FIX IS HERE
                .filter(TestRequest.id == request_id)
                .first()
            )

            if not result_data:
                return None

            request, patient, result = result_data

            # Use 'full_name' and 'gender' from your 'patients' table describe output
            return {
                "metadata": {
                    "request_id": request.id,
                    "status": request.status,
                    "created_at": request.created_at.isoformat(),
                },
                "patient": {
                    "name": patient.full_name, # Match your 'full_name' column
                    "age": "N/A", # You have 'date_of_birth', you'd need to calculate age
                    "sex": patient.gender,    # Match your 'gender' column
                    "uid": f"PAT-{patient.id:04d}"
                },
                "clinical_data": {
                    "results": result.values if result else {},
                    "flags": result.flags if result else {},
                    "snapshot": result.template_snapshot if result else {},
                    "notes": result.notes if result else ""
                }
            }
        except Exception as e:
            print(f"Service Error: {e}")
            raise e