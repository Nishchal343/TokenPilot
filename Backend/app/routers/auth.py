from datetime import datetime, timezone
from fastapi import APIRouter, Depends, HTTPException, Request, status
from fastapi.responses import JSONResponse
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.core.security import hash_password, verify_password, create_access_token
from app.models.company import Company
from app.models.employee import Employee
from app.models.invitation import Invitation
from app.models.enums import OTPPurpose, EmployeeRole, InvitationStatus, InvitedByType, OfferedRole
from app.models.security_log import SecurityLog
from app.services.notification_service import create_notification
from app.services.email_service import email_service
from app.services.otp_service import otp_service
from app.schemas.auth import MessageResponse, TokenResponse
from app.schemas.company import (
    CompanyRegisterRequest,
    CompanyVerifyOTPRequest,
    CompanyLoginRequest,
    CompanyForgotPasswordRequest,
    CompanyResetPasswordRequest,
    CompanyResponse,
)
from app.schemas.employee import (
    EmployeeRegisterRequest,
    EmployeeVerifyOTPRequest,
    EmployeeLoginRequest,
    EmployeeForgotPasswordRequest,
    EmployeeResetPasswordRequest,
    EmployeeResponse,
)

router = APIRouter(prefix="/auth", tags=["Authentication"])


# --- Company Authentication Endpoints ---

@router.post("/company/register", response_model=MessageResponse, status_code=status.HTTP_201_CREATED)
def company_register(payload: CompanyRegisterRequest, db: Session = Depends(get_db)):
    if payload.password != payload.confirm_password:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Passwords do not match"
        )
        
    # Check if email is already taken in companies or employees
    existing_co = db.query(Company).filter(Company.email == payload.email).first()
    existing_emp = db.query(Employee).filter(Employee.email == payload.email).first()
    if existing_emp:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Email already registered"
        )

    if existing_co:
        if not existing_co.is_verified:
            otp = otp_service.create_otp(db, payload.email, OTPPurpose.register)
            email_service.send_otp_email(payload.email, otp)
            return JSONResponse(
                status_code=status.HTTP_200_OK,
                content={"message": "This email has not been verified yet. A new verification code has been sent."},
            )
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Email already registered"
        )
        
    # Create company
    pwd_hash = hash_password(payload.password)
    new_company = Company(
        name=payload.name,
        email=payload.email,
        password_hash=pwd_hash,
        is_verified=False
    )
    db.add(new_company)
    db.commit()
    db.refresh(new_company)
    
    # Generate and send OTP
    otp = otp_service.create_otp(db, payload.email, OTPPurpose.register)
    email_service.send_otp_email(payload.email, otp)
    
    return {"message": "Company registered successfully. Verification OTP sent to email."}


@router.post("/company/verify-otp", response_model=TokenResponse)
def company_verify_otp(payload: CompanyVerifyOTPRequest, db: Session = Depends(get_db)):
    otp_record = otp_service.verify_otp(db, payload.email, payload.otp, OTPPurpose.register)
    if not otp_record:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Invalid or expired OTP"
        )
        
    company = db.query(Company).filter(Company.email == payload.email).first()
    if not company:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Company not found"
        )
        
    # Verify company
    company.is_verified = True
    otp_service.mark_otp_used(db, otp_record)
    db.commit()
    
    # Generate JWT
    token_payload = {
        "type": "company",
        "company_id": company.id
    }
    access_token = create_access_token(data=token_payload)
    return {"access_token": access_token, "token_type": "bearer"}


@router.post("/company/login", response_model=TokenResponse)
def company_login(payload: CompanyLoginRequest, request: Request, db: Session = Depends(get_db)):
    company = db.query(Company).filter(Company.email == payload.email).first()
    if not company or not verify_password(payload.password, company.password_hash):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Incorrect email or password"
        )
        
    if not company.is_verified:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Email not verified. Please verify your email first."
        )

    # Record login
    now = datetime.now(timezone.utc)
    company.last_login_at = now
    db.add(SecurityLog(user_type="company", user_id=company.id, event_type="login", ip_address=request.client.host if request.client else None))
    db.commit()
        
    token_payload = {
        "type": "company",
        "company_id": company.id
    }
    access_token = create_access_token(data=token_payload)
    return {"access_token": access_token, "token_type": "bearer"}


@router.post("/company/forgot-password", response_model=MessageResponse)
def company_forgot_password(payload: CompanyForgotPasswordRequest, db: Session = Depends(get_db)):
    company = db.query(Company).filter(Company.email == payload.email).first()
    if company:
        otp = otp_service.create_otp(db, payload.email, OTPPurpose.reset_password)
        email_service.send_otp_email(payload.email, otp)
    
    return {"message": "If the email is registered, a password reset OTP has been sent."}


@router.post("/company/reset-password", response_model=MessageResponse)
def company_reset_password(payload: CompanyResetPasswordRequest, db: Session = Depends(get_db)):
    if payload.new_password != payload.confirm_password:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Passwords do not match"
        )
        
    otp_record = otp_service.verify_otp(db, payload.email, payload.otp, OTPPurpose.reset_password)
    if not otp_record:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Invalid or expired OTP"
        )
        
    company = db.query(Company).filter(Company.email == payload.email).first()
    if not company:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Company not found"
        )
        
    company.password_hash = hash_password(payload.new_password)
    otp_service.mark_otp_used(db, otp_record)
    db.commit()
    
    return {"message": "Password reset successfully."}


# --- Employee Authentication Endpoints ---


def _join_pending_invitation(db: Session, employee: Employee) -> bool:
    """Join the newest valid pending invitation for a verified employee."""
    now = datetime.now(timezone.utc)
    invitation = (
        db.query(Invitation)
        .filter(
            Invitation.email == employee.email,
            Invitation.status == InvitationStatus.pending,
        )
        .order_by(Invitation.created_at.desc())
        .first()
    )
    if not invitation:
        return False

    if invitation.token_expires_at < now:
        invitation.status = InvitationStatus.expired
        db.commit()
        return False

    if invitation.invited_by_type == InvitedByType.company:
        company_id = invitation.company_id or invitation.invited_by_id
        invited_by_id = None
    else:
        inviter = db.query(Employee).filter(Employee.id == invitation.invited_by_id).first()
        if not inviter or not inviter.company_id:
            return False
        if invitation.company_id != inviter.company_id or invitation.manager_id != inviter.id or inviter.role != EmployeeRole.manager:
            return False
        company_id = inviter.company_id
        invited_by_id = inviter.id

    employee.company_id = company_id
    employee.invited_by_id = invited_by_id
    employee.manager_id = invitation.manager_id
    employee.role = EmployeeRole.manager if invitation.role_offered == OfferedRole.manager else EmployeeRole.employee
    invitation.status = InvitationStatus.accepted
    invitation.accepted_at = now

    create_notification(
        db,
        employee,
        "Invitation accepted",
        "Your account has joined the organization.",
        "invitation_accepted",
        send_email=False,
    )
    if invitation.invited_by_type == InvitedByType.employee:
        inviter = db.query(Employee).filter(Employee.id == invitation.invited_by_id).first()
        if inviter:
            create_notification(
                db,
                inviter,
                "Invitation accepted",
                f"{employee.email} accepted your invitation.",
                "invitation_accepted",
                send_email=False,
            )
    return True

@router.post("/employee/register", response_model=MessageResponse, status_code=status.HTTP_201_CREATED)
def employee_register(payload: EmployeeRegisterRequest, db: Session = Depends(get_db)):
    if payload.password != payload.confirm_password:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Passwords do not match"
        )
        
    # Check if employee already exists
    existing_emp = db.query(Employee).filter(Employee.email == payload.email).first()
    if existing_emp:
        if not existing_emp.is_verified:
            otp = otp_service.create_otp(db, payload.email, OTPPurpose.register)
            email_service.send_otp_email(payload.email, otp)
            return JSONResponse(
                status_code=status.HTTP_200_OK,
                content={"message": "This email has not been verified yet. A new verification code has been sent."},
            )
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="An employee account with this email already exists."
        )

    if db.query(Company).filter(Company.email == payload.email).first():
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="A company account with this email already exists."
        )
        
    # Create employee (unverified, no company linked yet)
    pwd_hash = hash_password(payload.password)
    new_employee = Employee(
        name=payload.name,
        email=payload.email,
        password_hash=pwd_hash,
        is_verified=False,
        role=EmployeeRole.employee,
    )
    
    db.add(new_employee)
    db.commit()
    
    # Generate and send OTP
    otp = otp_service.create_otp(db, payload.email, OTPPurpose.register)
    email_service.send_otp_email(payload.email, otp)
    
    return {"message": "Employee registered successfully. Verification OTP sent to email."}


@router.post("/employee/verify-otp", response_model=TokenResponse)
def employee_verify_otp(payload: EmployeeVerifyOTPRequest, db: Session = Depends(get_db)):
    otp_record = otp_service.verify_otp(db, payload.email, payload.otp, OTPPurpose.register)
    if not otp_record:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Invalid or expired OTP"
        )
        
    employee = db.query(Employee).filter(Employee.email == payload.email).first()
    if not employee:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Employee not found"
        )

    employee.is_verified = True
    _join_pending_invitation(db, employee)
    otp_service.mark_otp_used(db, otp_record)
    db.commit()
    db.refresh(employee)
    
    # Generate JWT
    token_payload = {
        "type": "employee",
        "employee_id": employee.id,
        "company_id": employee.company_id,
        "role": employee.role.value if employee.role else None,
        "manager_id": employee.manager_id,
    }
    access_token = create_access_token(data=token_payload)
    return {"access_token": access_token, "token_type": "bearer"}


@router.post("/employee/login", response_model=TokenResponse)
def employee_login(payload: EmployeeLoginRequest, request: Request, db: Session = Depends(get_db)):
    employee = db.query(Employee).filter(Employee.email == payload.email).first()
    if not employee or not verify_password(payload.password, employee.password_hash):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Incorrect email or password"
        )
        
    if not employee.is_verified:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Employee account is not verified."
        )

    # Record login
    now = datetime.now(timezone.utc)
    employee.last_login_at = now
    db.add(SecurityLog(user_type="employee", user_id=employee.id, event_type="login", ip_address=request.client.host if request.client else None))
    db.commit()
        
    token_payload = {
        "type": "employee",
        "employee_id": employee.id,
        "company_id": employee.company_id,
        "role": employee.role.value if employee.role else None,
        "manager_id": employee.manager_id,
    }
    access_token = create_access_token(data=token_payload)
    return {"access_token": access_token, "token_type": "bearer"}


@router.post("/employee/forgot-password", response_model=MessageResponse)
def employee_forgot_password(payload: EmployeeForgotPasswordRequest, db: Session = Depends(get_db)):
    employee = db.query(Employee).filter(Employee.email == payload.email).first()
    if employee:
        otp = otp_service.create_otp(db, payload.email, OTPPurpose.reset_password)
        email_service.send_otp_email(payload.email, otp)
        
    return {"message": "If the email is registered, a password reset OTP has been sent."}


@router.post("/employee/reset-password", response_model=MessageResponse)
def employee_reset_password(payload: EmployeeResetPasswordRequest, db: Session = Depends(get_db)):
    if payload.new_password != payload.confirm_password:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Passwords do not match"
        )
        
    otp_record = otp_service.verify_otp(db, payload.email, payload.otp, OTPPurpose.reset_password)
    if not otp_record:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Invalid or expired OTP"
        )
        
    employee = db.query(Employee).filter(Employee.email == payload.email).first()
    if not employee:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Employee not found"
        )
        
    employee.password_hash = hash_password(payload.new_password)
    otp_service.mark_otp_used(db, otp_record)
    db.commit()
    
    return {"message": "Password reset successfully."}
