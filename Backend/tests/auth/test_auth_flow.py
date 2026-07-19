import uuid
from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from app.main import app
from app.core.database import SessionLocal
from app.models.company import Company
from app.models.employee import Employee
from app.models.invitation import Invitation
from app.models.otp import OTP
from app.models.enums import OTPPurpose, EmployeeRole, InvitationStatus, InvitedByType, OfferedRole

client = TestClient(app)


def get_cleanup_email(prefix: str) -> str:
    return f"{prefix}_{uuid.uuid4().hex[:6]}@example.com"


def test_complete_company_and_employee_flow():
    db = SessionLocal()
    
    # 1. Register Company
    company_email = get_cleanup_email("company")
    company_name = "Test Enterprise"
    
    reg_response = client.post(
        "/auth/company/register",
        json={
            "name": company_name,
            "email": company_email,
            "password": "password123",
            "confirm_password": "password123"
        }
    )
    assert reg_response.status_code == 201
    assert "Verification OTP sent" in reg_response.json()["message"]
    
    # Check that Company exists in DB and is not verified
    company_db = db.query(Company).filter(Company.email == company_email).first()
    assert company_db is not None
    assert company_db.is_verified is False
    
    # 2. Retrieve OTP and Verify Company
    otp_record = db.query(OTP).filter(
        OTP.email == company_email,
        OTP.purpose == OTPPurpose.register,
        OTP.is_used.is_(False)
    ).first()
    assert otp_record is not None
    
    verify_response = client.post(
        "/auth/company/verify-otp",
        json={
            "email": company_email,
            "otp": otp_record.otp_code
        }
    )
    assert verify_response.status_code == 200
    company_token = verify_response.json()["access_token"]
    assert company_token is not None
    
    # Refresh and check verification status
    db.refresh(company_db)
    assert company_db.is_verified is True
    
    # 3. Company Login
    login_response = client.post(
        "/auth/company/login",
        json={
            "email": company_email,
            "password": "password123"
        }
    )
    assert login_response.status_code == 200
    assert login_response.json()["access_token"] is not None
    
    # 4. Company Forgot Password & Reset Password
    forgot_response = client.post(
        "/auth/company/forgot-password",
        json={"email": company_email}
    )
    assert forgot_response.status_code == 200
    
    reset_otp_record = db.query(OTP).filter(
        OTP.email == company_email,
        OTP.purpose == OTPPurpose.reset_password,
        OTP.is_used.is_(False)
    ).first()
    assert reset_otp_record is not None
    
    reset_response = client.post(
        "/auth/company/reset-password",
        json={
            "email": company_email,
            "otp": reset_otp_record.otp_code,
            "new_password": "newpassword123",
            "confirm_password": "newpassword123"
        }
    )
    assert reset_response.status_code == 200
    
    # Login with new password
    login_new_response = client.post(
        "/auth/company/login",
        json={
            "email": company_email,
            "password": "newpassword123"
        }
    )
    assert login_new_response.status_code == 200
    company_token = login_new_response.json()["access_token"]
    
    # 5. Company Invites Team Lead (Manager role)
    manager_email = get_cleanup_email("manager")
    headers = {"Authorization": f"Bearer {company_token}"}
    
    invite_mgr_response = client.post(
        "/invitations/send",
        json={
            "employee_email": manager_email,
            "role": "manager"
        },
        headers=headers
    )
    assert invite_mgr_response.status_code == 200
    
    # Check Invitation in DB
    invitation_db = db.query(Invitation).filter(
        Invitation.email == manager_email,
        Invitation.status == InvitationStatus.pending
    ).first()
    assert invitation_db is not None
    assert invitation_db.role_offered == OfferedRole.manager
    
    # 6. Verify Invitation Token (Public endpoint)
    verify_invite_response = client.get(f"/invitations/verify/{invitation_db.token}")
    assert verify_invite_response.status_code == 200
    assert verify_invite_response.json()["email"] == manager_email
    assert verify_invite_response.json()["role_offered"] == "manager"
    assert verify_invite_response.json()["account_exists"] is False
    
    # 7. Employee registers publicly; the pending invitation is matched by email
    emp_reg_response = client.post(
        "/auth/employee/register",
        json={
            "name": "Team Lead One",
            "email": manager_email,
            "password": "managerpassword",
            "confirm_password": "managerpassword"
        }
    )
    assert emp_reg_response.status_code == 201
    manager_otp = db.query(OTP).filter(
        OTP.email == manager_email,
        OTP.purpose == OTPPurpose.register,
        OTP.is_used.is_(False),
    ).first()
    manager_verify = client.post(
        "/auth/employee/verify-otp",
        json={"email": manager_email, "otp": manager_otp.otp_code},
    )
    assert manager_verify.status_code == 200
    manager_token = manager_verify.json()["access_token"]
    
    # Validate manager in DB
    manager_db = db.query(Employee).filter(Employee.email == manager_email).first()
    assert manager_db is not None
    assert manager_db.role == EmployeeRole.manager
    assert manager_db.company_id == company_db.id
    assert manager_db.is_verified is True
    
    # Refresh invitation and check status
    db.refresh(invitation_db)
    assert invitation_db.status == InvitationStatus.accepted
    
    # 8. Manager logins
    mgr_login_response = client.post(
        "/auth/employee/login",
        json={
            "email": manager_email,
            "password": "managerpassword"
        }
    )
    assert mgr_login_response.status_code == 200
    assert mgr_login_response.json()["access_token"] is not None
    
    # 9. Manager Invites Team Member (Employee role)
    member_email = get_cleanup_email("member")
    mgr_headers = {"Authorization": f"Bearer {manager_token}"}
    
    invite_mem_response = client.post(
        "/invitations/send",
        json={
            "employee_email": member_email,
            "role": "employee"
        },
        headers=mgr_headers
    )
    assert invite_mem_response.status_code == 200
    
    member_invite_db = db.query(Invitation).filter(
        Invitation.email == member_email,
        Invitation.status == InvitationStatus.pending
    ).first()
    assert member_invite_db is not None
    assert member_invite_db.role_offered == OfferedRole.employee
    assert member_invite_db.invited_by_type == InvitedByType.employee
    assert member_invite_db.invited_by_id == manager_db.id
    
    # 10. Enforce Manager CANNOT invite another Manager
    sub_manager_email = get_cleanup_email("sub_manager")

    invite_sub_mgr_response = client.post(
        "/invitations/send",
        json={
            "employee_email": sub_manager_email,
            "role": "manager"
        },
        headers=mgr_headers
    )

    assert invite_sub_mgr_response.status_code == 200

    sub_manager_invite_db = db.query(Invitation).filter(
        Invitation.email == sub_manager_email,
        Invitation.status == InvitationStatus.pending
    ).first()

    assert sub_manager_invite_db is not None
    assert sub_manager_invite_db.role_offered == OfferedRole.manager
    assert sub_manager_invite_db.invited_by_type == InvitedByType.employee
    assert sub_manager_invite_db.invited_by_id == manager_db.id
    
    # 11. Team Member signup; the pending invitation is matched by email
    mem_reg_response = client.post(
        "/auth/employee/register",
        json={
            "name": "Team Member One",
            "email": member_email,
            "password": "memberpassword",
            "confirm_password": "memberpassword"
        }
    )
    assert mem_reg_response.status_code == 201
    member_otp = db.query(OTP).filter(
        OTP.email == member_email,
        OTP.purpose == OTPPurpose.register,
        OTP.is_used.is_(False),
    ).first()
    member_verify = client.post(
        "/auth/employee/verify-otp",
        json={"email": member_email, "otp": member_otp.otp_code},
    )
    assert member_verify.status_code == 200
    member_token = member_verify.json()["access_token"]
    
    # Validate member in DB
    member_db = db.query(Employee).filter(Employee.email == member_email).first()
    assert member_db is not None
    assert member_db.role == EmployeeRole.employee
    assert member_db.company_id == company_db.id
    assert member_db.invited_by_id == manager_db.id
    
    # 12. Team Member attempts to invite someone (Should fail 403)
    mem_headers = {"Authorization": f"Bearer {member_token}"}
    unauthorized_invite = client.post(
        "/invitations/send",
        json={
            "employee_email": get_cleanup_email("underling"),
            "role": "employee"
        },
        headers=mem_headers
    )
    assert unauthorized_invite.status_code == 403
    
    # Cleanup DB records
    if member_db:
        db.delete(member_db)

    if manager_db:
        db.delete(manager_db)

    if sub_manager_invite_db:
        db.delete(sub_manager_invite_db)

    if invitation_db:
        db.delete(invitation_db)

    if member_invite_db:
        db.delete(member_invite_db)

    if company_db:
        db.delete(company_db)
    if otp_record:
        db.delete(otp_record)
    if reset_otp_record:
        db.delete(reset_otp_record)
    db.commit()
    db.close()
