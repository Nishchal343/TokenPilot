import logging

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.core.dependencies import get_current_token_payload
from app.models.company import Company
from app.models.employee import Employee
from app.models.security_log import SecurityLog
from app.schemas.security import SecurityInfoResponse, SecurityLogEntry

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/security", tags=["Security"])


@router.get("/info", response_model=SecurityInfoResponse)
def get_security_info(
    db: Session = Depends(get_db),
    payload: dict = Depends(get_current_token_payload),
):
    user_type = payload.get("type")
    if user_type == "company":
        user = db.query(Company).filter(Company.id == payload["company_id"]).first()
        role = "Company Admin"
    else:
        user = db.query(Employee).filter(Employee.id == payload["employee_id"]).first()
        role = "Team Lead" if user and user.role and user.role.value == "manager" else "Employee"

    recent_logs = (
        db.query(SecurityLog)
        .filter(SecurityLog.user_type == user_type, SecurityLog.user_id == user.id)
        .order_by(SecurityLog.created_at.desc())
        .limit(10)
        .all()
    )

    return {
        "email": user.email,
        "is_verified": user.is_verified,
        "role": role,
        "last_login_at": user.last_login_at,
        "created_at": user.created_at,
        "recent_logins": [
            {"event_type": log.event_type, "ip_address": log.ip_address, "created_at": log.created_at}
            for log in recent_logs
        ],
    }
