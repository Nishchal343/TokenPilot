import logging
from datetime import datetime, timezone

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.core.dependencies import get_current_token_payload
from app.core.security import hash_password, verify_password
from app.models.company import Company
from app.models.employee import Employee
from app.models.enums import OTPPurpose
from app.models.security_log import SecurityLog
from app.models.otp import OTP
from app.services.otp_service import otp_service
from app.services.email_service import email_service
from app.schemas.auth import MessageResponse
from app.schemas.support import ChangePasswordRequest, ChangePasswordVerifyRequest

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/settings", tags=["Settings"])


@router.post("/change-password/request", response_model=MessageResponse)
def change_password_request(
    body: ChangePasswordRequest,
    db: Session = Depends(get_db),
    payload: dict = Depends(get_current_token_payload),
):
    if body.new_password != body.confirm_password:
        raise HTTPException(status_code=400, detail="New password and confirmation do not match.")

    if len(body.new_password) < 8:
        raise HTTPException(status_code=400, detail="Password must be at least 8 characters long.")

    if body.new_password == body.current_password:
        raise HTTPException(status_code=400, detail="New password must be different from the current password.")

    user_type = payload.get("type")
    if user_type == "company":
        user = db.query(Company).filter(Company.id == payload["company_id"]).first()
    else:
        user = db.query(Employee).filter(Employee.id == payload["employee_id"]).first()

    if not user:
        raise HTTPException(status_code=404, detail="User not found.")

    if not verify_password(body.current_password, user.password_hash):
        raise HTTPException(status_code=400, detail="Current password is incorrect.")

    # Generate and send OTP
    otp = otp_service.create_otp(db, user.email, OTPPurpose.change_password)
    email_sent = email_service.send_otp_email(user.email, otp, purpose="password change")
    if not email_sent:
        db.rollback()
        raise HTTPException(status_code=500, detail="Failed to send OTP email.")

    logger.info("Password change OTP requested and sent to %s", user.email)
    return {"message": "Verification code has been sent to your registered email."}


@router.post("/change-password/verify", response_model=MessageResponse)
def change_password_verify(
    body: ChangePasswordVerifyRequest,
    db: Session = Depends(get_db),
    payload: dict = Depends(get_current_token_payload),
):
    if body.new_password != body.confirm_password:
        raise HTTPException(status_code=400, detail="New password and confirmation do not match.")

    if len(body.new_password) < 8:
        raise HTTPException(status_code=400, detail="Password must be at least 8 characters long.")

    user_type = payload.get("type")
    if user_type == "company":
        user = db.query(Company).filter(Company.id == payload["company_id"]).first()
    else:
        user = db.query(Employee).filter(Employee.id == payload["employee_id"]).first()

    if not user:
        raise HTTPException(status_code=404, detail="User not found.")

    # Find the latest active OTP for this email
    otp_record = (
        db.query(OTP)
        .filter(
            OTP.email == user.email,
            OTP.purpose == OTPPurpose.change_password,
            OTP.is_used.is_(False),
        )
        .order_by(OTP.created_at.desc())
        .first()
    )

    if not otp_record:
        raise HTTPException(status_code=400, detail="No active verification code found.")

    # Check attempt limit
    otp_record.attempts += 1
    db.commit()

    if otp_record.attempts > 3:
        otp_record.is_used = True
        db.commit()
        raise HTTPException(
            status_code=400,
            detail="Too many failed attempts. This verification code has been invalidated. Please request a new one."
        )

    # Check expiry
    current_time = datetime.now(timezone.utc)
    if otp_record.expires_at < current_time:
        otp_record.is_used = True
        db.commit()
        raise HTTPException(status_code=400, detail="Verification code has expired. Please request a new one.")

    # Verify code
    if otp_record.otp_code != body.otp:
        remaining = 3 - otp_record.attempts
        if remaining <= 0:
            otp_record.is_used = True
            db.commit()
            raise HTTPException(
                status_code=400,
                detail="Incorrect code. Too many failed attempts. This code has been invalidated."
            )
        raise HTTPException(
            status_code=400,
            detail=f"Incorrect verification code. {remaining} attempt(s) remaining."
        )

    # All checks passed: update password
    user.password_hash = hash_password(body.new_password)
    otp_record.is_used = True

    # Log the password change
    log = SecurityLog(
        user_type=user_type,
        user_id=user.id,
        event_type="password_change",
    )
    db.add(log)
    db.commit()

    logger.info("Password changed successfully after OTP verification for %s id=%s", user_type, user.id)
    return {"message": "Your password has been updated successfully."}
