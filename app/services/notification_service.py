from sqlalchemy.orm import Session
from app.models.notification_model import Notification
import requests
import os
import logging
import sys

# Configure logging to output to stdout so Render captures it immediately
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    handlers=[logging.StreamHandler(sys.stdout)]
)
logger = logging.getLogger(__name__)

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
        notification = db.query(Notification).filter(Notification.id == notification_id).first()
        if notification:
            notification.is_read = True
            db.commit()
        return notification

    # ==========================================================
    # SENDCHAMP SMS DELIVERY LAYER (Bulletproof Version)
    # ==========================================================
    @staticmethod
    def send_sms(phone: str, message: str) -> None:
        """
        SMS delivery via Sendchamp with heavy logging for Render.
        """
        logger.info(f"[SMS ATTEMPT] Preparing to send to: {phone}")

        api_key = os.getenv("SENDCHAMP_API_KEY")
        if not api_key:
            logger.error("[SMS ABORTED] SENDCHAMP_API_KEY is missing from Environment Variables.")
            return

        # Normalization
        original_phone = phone
        phone = NotificationService._normalize_phone(phone).replace("+", "")
        logger.info(f"[SMS DATA] Normalized {original_phone} -> {phone}")

        url = "https://api.sendchamp.com/api/v1/sms/send"
        
        headers = {
            "Accept": "application/json",
            "Content-Type": "application/json",
            "Authorization": f"Bearer {api_key}"
        }

        payload = {
            "to": [phone],
            "message": message,
            "sender_name": "IandELabs", 
            "route": "non_dnd"
        }

        try:
            logger.info(f"[SMS REQUEST] Sending POST to Sendchamp for {phone}...")
            resp = requests.post(url, json=payload, headers=headers, timeout=15)
            
            # Check if we even got a response
            logger.info(f"[SMS RESPONSE] Status Code: {resp.status_code}")
            
            resp_data = resp.json() if resp.content else {}
            
            if resp.status_code in [200, 201] and resp_data.get("status") == "success":
                logger.info(f"[SMS SUCCESS] Sendchamp accepted the message for {phone}. ID: {resp_data.get('data', {}).get('id', 'N/A')}")
            else:
                logger.warning(f"[SMS FAIL] Sendchamp rejected request. Response: {resp.text}")

        except requests.exceptions.Timeout:
            logger.error(f"[SMS ERROR] Connection to Sendchamp timed out for {phone}.")
        except requests.exceptions.RequestException as e:
            logger.error(f"[SMS ERROR] Network issue or invalid URL: {e}")
        except Exception as e:
            logger.error(f"[SMS CRITICAL] Unexpected error: {str(e)}")

    # ==========================================================
    # PHONE NORMALIZATION
    # ==========================================================
    @staticmethod
    def _normalize_phone(phone: str) -> str:
        if not phone:
            return ""

        # Remove everything except digits
        clean_digits = "".join(filter(str.isdigit, phone.strip()))

        # If it starts with 0 (local Nigeria), convert to 234
        if clean_digits.startswith("0") and len(clean_digits) == 11:
            return "234" + clean_digits[1:]

        # If it's already 234...
        if clean_digits.startswith("234") and len(clean_digits) >= 11:
            return clean_digits

        # If it's short, it might be a wrong number
        if len(clean_digits) < 10:
            logger.warning(f"[SMS VALIDATION] Phone number {phone} seems too short.")

        return clean_digits
