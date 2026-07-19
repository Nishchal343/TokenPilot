from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.core.dependencies import get_current_token_payload
from app.models.notification import Notification
from app.schemas.auth import MessageResponse
from app.schemas.notification import NotificationResponse

router = APIRouter(prefix="/notifications", tags=["Notifications"])


def _get_employee_id(payload: dict) -> int | None:
    """Return employee_id from payload; company tokens have no notifications."""
    if payload.get("type") == "employee":
        return payload.get("employee_id")
    return None


@router.get("", response_model=list[NotificationResponse])
def get_my_notifications(db: Session = Depends(get_db), payload: dict = Depends(get_current_token_payload)):
    employee_id = _get_employee_id(payload)
    if not employee_id:
        return []
    return db.query(Notification).filter(Notification.employee_id == employee_id).order_by(Notification.created_at.desc()).all()


@router.patch("/{notification_id}/read", response_model=MessageResponse)
def mark_read(notification_id: int, db: Session = Depends(get_db), payload: dict = Depends(get_current_token_payload)):
    employee_id = _get_employee_id(payload)
    if not employee_id:
        raise HTTPException(status_code=403, detail="Company accounts do not have notifications.")
    notification = db.query(Notification).filter(Notification.id == notification_id, Notification.employee_id == employee_id).first()
    if not notification:
        raise HTTPException(status_code=404, detail="Notification not found.")
    notification.is_read = True
    db.commit()
    return {"message": "Notification marked as read."}


@router.post("/read-all", response_model=MessageResponse)
def mark_all_read(db: Session = Depends(get_db), payload: dict = Depends(get_current_token_payload)):
    employee_id = _get_employee_id(payload)
    if not employee_id:
        return {"message": "No notifications to mark."}
    db.query(Notification).filter(Notification.employee_id == employee_id, Notification.is_read.is_(False)).update({Notification.is_read: True})
    db.commit()
    return {"message": "All notifications marked as read."}


@router.delete("/{notification_id}", response_model=MessageResponse)
def delete_notification(notification_id: int, db: Session = Depends(get_db), payload: dict = Depends(get_current_token_payload)):
    employee_id = _get_employee_id(payload)
    if not employee_id:
        raise HTTPException(status_code=403, detail="Company accounts do not have notifications.")
    notification = db.query(Notification).filter(Notification.id == notification_id, Notification.employee_id == employee_id).first()
    if not notification:
        raise HTTPException(status_code=404, detail="Notification not found.")
    db.delete(notification)
    db.commit()
    return {"message": "Notification deleted."}
