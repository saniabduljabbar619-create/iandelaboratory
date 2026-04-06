# app/services/notification_service.py
from sqlalchemy.orm import Session
from app.models.notification_model import Notification
import requests
import os

class NotificationService:

    @staticmethod
    def create(
        db: Session,
        type: str,
        title: str,
        message: str,
        reference_type: str = None,
        reference_id: int = None
    ) -> Notification:

        notification = Notification(
            type=type,
            title=title,
            message=message,
            reference_type=reference_type,
            reference_id=reference_id
        )

        db.add(notification)
        db.commit()
        db.refresh(notification)
        return notification

    @staticmethod
    def list_recent(db: Session, limit: int = 20):
        return (
            db.query(Notification)
            .order_by(Notification.created_at.desc())
            .limit(limit)
            .all()
        )

    @staticmethod
    def unread_count(db: Session) -> int:
        return (
            db.query(Notification)
            .filter(Notification.is_read == False)
            .count()
        )

    @staticmethod
    def mark_read(db: Session, notification_id: int):
        notification = (
            db.query(Notification)
            .filter(Notification.id == notification_id)
            .first()
        )
        if notification:
            notification.is_read = True
            db.commit()
        return notification

    # ==========================================================
    # SMS DELIVERY LAYER
    # ==========================================================
    @staticmethod
    def send_sms(phone: str, message: str) -> None:
        """
        Sends SMS via Termii.
        Safe: will not crash main workflow.
        Works for feature phones and smartphones.
        """
        api_key = os.getenv("TERMII_API_KEY")
        if not api_key:
            print("[SMS] Skipped: TERMII_API_KEY not set")
            return

        phone = NotificationService._normalize_phone(phone)

        url = "https://api.ng.termii.com/api/sms/send"

        payload = {
            "to": phone,
            "from": "IEDLABS",      # must match approved sender
            "sms": message,
            "type": "plain",
            "channel": "transactional",  # ensures delivery to smartphones
            "api_key": api_key
        }

        try:
            resp = requests.post(url, json=payload, timeout=10)
            resp_data = resp.json() if resp.content else {}

            if resp.status_code != 200 or resp_data.get("status") != "success":
                raise Exception(f"SMS Failed: {resp.text} | {resp_data}")

            print(f"[SMS SENT] -> {phone}")

        except Exception as e:
            # Do not break main workflow
            print(f"[SMS ERROR] {e}")

    # ==========================================================
    # PHONE NORMALIZATION (Nigeria-safe, Termii-friendly)
    # ==========================================================
    @staticmethod
    def _normalize_phone(phone: str) -> str:
        if not phone:
            return phone

        phone = phone.strip()

        # Local 0-prefixed numbers → +234
        if phone.startswith("0") and len(phone) == 11:
            return "+234" + phone[1:]

        # Already +234
        if phone.startswith("+234") and len(phone) >= 13:
            return phone

        # Already international (assume valid)
        if phone.startswith("+") and len(phone) >= 11:
            return phone

        # Fallback: leave as-is but warn
        print(f"[SMS WARNING] Unknown phone format: {phone}")
        return phone