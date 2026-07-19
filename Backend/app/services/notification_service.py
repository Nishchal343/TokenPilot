from app.models.employee import Employee
from app.models.notification import Notification
from app.services.email_service import email_service


def create_notification(db, employee: Employee, title: str, message: str, event_type: str, send_email: bool = True):
    notification = Notification(
        employee_id=employee.id,
        title=title,
        message=message,
        type=event_type,
    )
    db.add(notification)
    if send_email:
        email_service.send_notification_email(employee.email, title, message)
    return notification
