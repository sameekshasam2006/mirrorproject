from datetime import datetime, timezone

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.core.security import get_current_active_user
from app.db import get_db
from app.models.models import Notification, PushSubscription, User

router = APIRouter()


@router.get("/")
def list_notifications(db: Session = Depends(get_db), current_user: User = Depends(get_current_active_user)):
    notifications = db.query(Notification).filter(Notification.user_id == current_user.id).order_by(Notification.created_at.desc()).all()
    return {"notifications": [
        {
            "id": item.id,
            "message": item.message,
            "delivery_status": item.delivery_status,
            "created_at": item.created_at.isoformat(),
        }
        for item in notifications
    ]}


@router.post("/push-subscription")
def save_push_subscription(payload: dict, db: Session = Depends(get_db), current_user: User = Depends(get_current_active_user)):
    if not payload.get("endpoint"):
        return {"status": "error", "message": "Missing endpoint"}
    existing = db.query(PushSubscription).filter(PushSubscription.user_id == current_user.id, PushSubscription.endpoint == payload["endpoint"]).first()
    if existing:
        return {"status": "saved", "id": existing.id}
    subscription = PushSubscription(
        user_id=current_user.id,
        endpoint=payload["endpoint"],
        p256dh=payload.get("keys", {}).get("p256dh", ""),
        auth=payload.get("keys", {}).get("auth", ""),
    )
    db.add(subscription)
    db.commit()
    return {"status": "saved"}


@router.patch("/{notification_id}/read")
def mark_notification_read(notification_id: int, db: Session = Depends(get_db), current_user: User = Depends(get_current_active_user)):
    notification = db.query(Notification).filter(Notification.id == notification_id, Notification.user_id == current_user.id).first()
    if not notification:
        return {"status": "not_found"}
    notification.read_at = datetime.now(timezone.utc).replace(tzinfo=None)
    notification.delivery_status = "read"
    db.commit()
    return {"status": "updated"}
