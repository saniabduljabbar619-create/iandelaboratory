from sqlalchemy.orm import Session

from app.models.notification_model import Notification


class NotificationService:

    @staticmethod
    def create(
        db: Session,
        type: str,
        title: str,
        message: str,
        reference_type: str = None,
        reference_id: int = None
    ):

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
    def unread_count(db: Session):

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