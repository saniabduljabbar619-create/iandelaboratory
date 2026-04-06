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
        Smart SMS sender with channel failover.
        Will NOT break workflow.
        """

        api_key = os.getenv("TERMII_API_KEY")
        if not api_key:
            print("[SMS] Skipped: TERMII_API_KEY not set")
            return

        phone = NotificationService._normalize_phone(phone)

        url = "https://api.ng.termii.com/api/sms/send"

        # Ordered fallback channels
        channels = ["transactional", "dnd", "generic"]

        for channel in channels:
            payload = {
                "to": phone,
                "from": "IEDLABS",
                "sms": message,
                "type": "plain",
                "channel": channel,
                "api_key": api_key
            }

            try:
                resp = requests.post(url, json=payload, timeout=10)
                resp_data = resp.json() if resp.content else {}

                is_success = (
                    resp.status_code == 200 and (
                        resp_data.get("status") == "success" or
                        resp_data.get("code") == "ok"
                    )
                )

                if is_success:
                    print(f"[SMS SENT - {channel}] -> {phone}")
                    return

                else:
                    print(f"[SMS FAIL - {channel}] {resp.text}")

            except Exception as e:
                print(f"[SMS ERROR - {channel}] {e}")

        print(f"[SMS FINAL FAIL] Could not deliver to {phone}")
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