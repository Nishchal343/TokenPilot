import logging
import secrets
from datetime import datetime, timedelta, timezone

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.core.config import settings
from app.core.dependencies import get_current_token_payload, get_current_company, get_current_employee, get_current_manager
from app.models.company import Company
from app.models.employee import Employee
from app.models.invitation import Invitation
from app.models.enums import InvitedByType, InvitationStatus, OfferedRole, EmployeeRole
from app.services.email_service import email_service
from app.services.notification_service import create_notification
from app.schemas.auth import MessageResponse
from app.schemas.invitation import (
    InviteRequest,
    InvitationListResponse,
    VerifyInvitationResponse,
    AcceptInvitationRequest,
    RejectInvitationRequest,
    MyInvitationResponse,
)

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/invitations", tags=["Invitations"])


@router.get("/mine", response_model=list[MyInvitationResponse])
def my_invitations(
    db: Session = Depends(get_db),
    employee=Depends(get_current_employee),
):
    """Return invitations for the signed-in employee, including pending actions."""
    now = datetime.now(timezone.utc)
    invitations = (
        db.query(Invitation)
        .filter(Invitation.email == employee.email)
        .order_by(Invitation.created_at.desc())
        .all()
    )

    result = []
    changed = False
    for invitation in invitations:
        if invitation.status == InvitationStatus.pending and invitation.token_expires_at < now:
            invitation.status = InvitationStatus.expired
            changed = True

        if invitation.invited_by_type == InvitedByType.company:
            company = db.query(Company).filter(Company.id == invitation.invited_by_id).first()
            company_name = company.name if company else "Organization"
            invited_by_name = company.name if company else "Organization admin"
        else:
            inviter = db.query(Employee).filter(Employee.id == invitation.invited_by_id).first()
            company = db.query(Company).filter(Company.id == inviter.company_id).first() if inviter and inviter.company_id else None
            company_name = company.name if company else "Organization"
            invited_by_name = inviter.name if inviter else "Team lead"

        result.append({
            "id": invitation.id,
            "email": invitation.email,
            "company_name": company_name,
            "invited_by_name": invited_by_name,
            "invited_by_type": invitation.invited_by_type,
            "role_offered": invitation.role_offered,
            "status": invitation.status,
            "token": invitation.token,
            "created_at": invitation.created_at,
            "token_expires_at": invitation.token_expires_at,
        })

    if changed:
        db.commit()
    return result


def get_current_inviter(
    db: Session = Depends(get_db),
    payload: dict = Depends(get_current_token_payload)
) -> dict:
    """
    Dependency that returns the current inviter information.
    The inviter can be a Company or an Employee with the Manager role.
    """
    token_type = payload.get("type")

    if token_type == "company":
        company_id = payload.get("company_id")
        company = db.query(Company).filter(Company.id == company_id).first()
        if not company or not company.is_verified:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Verified Company account required."
            )
        return {
            "invited_by_type": InvitedByType.company,
            "invited_by_id": company.id,
            "company_id": company.id,
            "inviter_name": company.name,
        }

    elif token_type == "employee":
        employee_id = payload.get("employee_id")
        employee = db.query(Employee).filter(Employee.id == employee_id).first()
        if not employee or not employee.is_verified:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Verified Employee account required."
            )
        if employee.role != EmployeeRole.manager:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Only managers (Team Leads) can invite team members."
            )
        return {
            "invited_by_type": InvitedByType.employee,
            "invited_by_id": employee.id,
            "company_id": employee.company_id,
            "inviter_name": employee.name,
        }

    else:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid authorization token type."
        )


def _get_company_name(db: Session, inviter: dict) -> str:
    """Get the company name from inviter context."""
    company = db.query(Company).filter(Company.id == inviter["company_id"]).first()
    return company.name if company else "Your Organization"


# ─── Invitation List (Company Admin Only) ────────────────────────────────────


@router.get("/list", response_model=list[InvitationListResponse])
def list_invitations(
    db: Session = Depends(get_db),
    company=Depends(get_current_company),
):
    """List all invitations for this company. Automatically marks expired ones."""
    now = datetime.now(timezone.utc)

    # Fetch all invitations sent by this company (or by employees in this company)
    company_employee_ids = [
        emp.id for emp in
        db.query(Employee.id).filter(Employee.company_id == company.id).all()
    ]

    invitations = (
        db.query(Invitation)
        .filter(
            (
                (Invitation.invited_by_type == InvitedByType.company) &
                (Invitation.invited_by_id == company.id)
            ) | (
                (Invitation.invited_by_type == InvitedByType.employee) &
                (Invitation.invited_by_id.in_(company_employee_ids))
            )
        )
        .order_by(Invitation.created_at.desc())
        .all()
    )

    # Auto-expire pending invitations that are past their deadline
    for inv in invitations:
        if inv.status == InvitationStatus.pending and inv.token_expires_at < now:
            inv.status = InvitationStatus.expired
    db.commit()

    return invitations


@router.get("/team", response_model=list[InvitationListResponse])
def list_team_invitations(
    db: Session = Depends(get_db),
    manager=Depends(get_current_manager),
):
    """List invitations sent by the signed-in manager only."""
    now = datetime.now(timezone.utc)
    invitations = (
        db.query(Invitation)
        .filter(
            Invitation.invited_by_type == InvitedByType.employee,
            Invitation.invited_by_id == manager.id,
        )
        .order_by(Invitation.created_at.desc())
        .all()
    )
    for invitation in invitations:
        if invitation.status == InvitationStatus.pending and invitation.token_expires_at < now:
            invitation.status = InvitationStatus.expired
    db.commit()
    return invitations


# ─── Send Invitation ─────────────────────────────────────────────────────────


@router.post("/send", response_model=MessageResponse)
def send_invitation(
    payload: InviteRequest,
    db: Session = Depends(get_db),
    inviter: dict = Depends(get_current_inviter),
):
    role_to_offer = payload.role
    if inviter["invited_by_type"] == InvitedByType.employee:
        role_to_offer = role_to_offer or OfferedRole.employee
        manager_id = inviter["invited_by_id"]
        if role_to_offer != OfferedRole.employee:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Managers can invite employees only.",
            )
    else:
        role_to_offer = role_to_offer or OfferedRole.employee
        manager_id = payload.manager_id
        if manager_id is not None:
            manager = db.query(Employee).filter(
                Employee.id == manager_id,
                Employee.company_id == inviter["company_id"],
                Employee.role == EmployeeRole.manager,
            ).first()
            if not manager:
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail="manager_id must reference a manager in this company.",
                )

    # Block if email belongs to a company account
    if db.query(Company).filter(Company.email == payload.employee_email).first():
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="A company account with this email already exists.",
        )

    if role_to_offer not in (OfferedRole.employee, OfferedRole.manager):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Invalid invitation role.",
        )

    # Check if already a member of this company
    existing_member = db.query(Employee).filter(
        Employee.email == payload.employee_email,
        Employee.company_id == inviter["company_id"],
    ).first()
    if existing_member:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="This person is already a member of your organization.",
        )

    inviter_employee = db.query(Employee).filter(Employee.id == manager_id).first() if inviter["invited_by_type"] == InvitedByType.employee else None
    if inviter["invited_by_type"] == InvitedByType.employee and (not inviter_employee or inviter_employee.role != EmployeeRole.manager):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Only managers can invite employees.",
        )

    if inviter["invited_by_type"] == InvitedByType.employee and payload.manager_id is not None:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Managers assign invitees to themselves.",
        )

    # Cancel previous pending invitations for this email
    existing_invites = (
        db.query(Invitation)
        .filter(
            Invitation.email == payload.employee_email,
            Invitation.status == InvitationStatus.pending,
        )
        .all()
    )
    now = datetime.now(timezone.utc)
    for invite in existing_invites:
        invite.status = InvitationStatus.cancelled
        invite.cancelled_at = now

    # Generate invitation token
    token = secrets.token_urlsafe(32)
    expires_at = now + timedelta(days=settings.INVITATION_EXPIRE_DAYS)

    new_invitation = Invitation(
        name=payload.employee_name,
        email=payload.employee_email,
        invited_by_type=inviter["invited_by_type"],
        invited_by_id=inviter["invited_by_id"],
        role_offered=role_to_offer,
        manager_id=manager_id,
        token=token,
        token_expires_at=expires_at,
        status=InvitationStatus.pending,
    )
    db.add(new_invitation)
    db.commit()

    # Notify existing employee
    existing_employee = db.query(Employee).filter(Employee.email == payload.employee_email).first()
    if existing_employee:
        create_notification(
            db, existing_employee, "Invitation received",
            f"You have been invited to join as {role_to_offer.value}.",
            "invitation_received",
        )
        db.commit()

    # Send email
    company_name = _get_company_name(db, inviter)
    role_label = "Manager" if role_to_offer == OfferedRole.manager else "Employee"
    email_service.send_invitation_email(
        recipient=payload.employee_email,
        invitation_token=token,
        company_name=company_name,
        inviter_name=inviter["inviter_name"],
        role_offered=role_label,
        expires_at=expires_at,
        account_exists=existing_employee is not None,
    )

    logger.info("Invitation sent to %s by %s (company_id=%s)", payload.employee_email, inviter["inviter_name"], inviter["company_id"])
    return {"message": f"Invitation sent successfully to {payload.employee_email}."}


# ─── Resend Invitation ───────────────────────────────────────────────────────


@router.post("/{invitation_id}/resend", response_model=MessageResponse)
def resend_invitation(
    invitation_id: int,
    db: Session = Depends(get_db),
    company=Depends(get_current_company),
):
    """Resend an invitation with a fresh token and expiry."""
    invitation = db.query(Invitation).filter(Invitation.id == invitation_id).first()
    if not invitation:
        raise HTTPException(status_code=404, detail="Invitation not found.")

    # Verify this invitation belongs to this company
    if invitation.invited_by_type == InvitedByType.company and invitation.invited_by_id != company.id:
        raise HTTPException(status_code=403, detail="Access denied.")
    if invitation.invited_by_type == InvitedByType.employee:
        inviter_emp = db.query(Employee).filter(Employee.id == invitation.invited_by_id).first()
        if not inviter_emp or inviter_emp.company_id != company.id:
            raise HTTPException(status_code=403, detail="Access denied.")

    if invitation.status not in (InvitationStatus.pending, InvitationStatus.expired):
        raise HTTPException(status_code=400, detail=f"Cannot resend a {invitation.status.value} invitation.")

    # Generate new token and expiry
    now = datetime.now(timezone.utc)
    invitation.token = secrets.token_urlsafe(32)
    invitation.token_expires_at = now + timedelta(days=settings.INVITATION_EXPIRE_DAYS)
    invitation.status = InvitationStatus.pending
    db.commit()

    # Send email
    role_label = "Manager" if invitation.role_offered == OfferedRole.manager else "Employee"
    email_service.send_invitation_email(
        recipient=invitation.email,
        invitation_token=invitation.token,
        company_name=company.name,
        inviter_name=company.name,
        role_offered=role_label,
        expires_at=invitation.token_expires_at,
        account_exists=db.query(Employee).filter(Employee.email == invitation.email).first() is not None,
    )

    logger.info("Invitation %s resent to %s", invitation_id, invitation.email)
    return {"message": f"Invitation resent to {invitation.email}."}


# ─── Cancel Invitation ───────────────────────────────────────────────────────


@router.post("/{invitation_id}/cancel", response_model=MessageResponse)
def cancel_invitation(
    invitation_id: int,
    db: Session = Depends(get_db),
    company=Depends(get_current_company),
):
    """Cancel a pending invitation."""
    invitation = db.query(Invitation).filter(Invitation.id == invitation_id).first()
    if not invitation:
        raise HTTPException(status_code=404, detail="Invitation not found.")

    if invitation.invited_by_type == InvitedByType.company and invitation.invited_by_id != company.id:
        raise HTTPException(status_code=403, detail="Access denied.")
    if invitation.invited_by_type == InvitedByType.employee:
        inviter_emp = db.query(Employee).filter(Employee.id == invitation.invited_by_id).first()
        if not inviter_emp or inviter_emp.company_id != company.id:
            raise HTTPException(status_code=403, detail="Access denied.")

    if invitation.status != InvitationStatus.pending:
        raise HTTPException(status_code=400, detail=f"Cannot cancel a {invitation.status.value} invitation.")

    invitation.status = InvitationStatus.cancelled
    invitation.cancelled_at = datetime.now(timezone.utc)
    db.commit()

    logger.info("Invitation %s cancelled", invitation_id)
    return {"message": "Invitation cancelled successfully."}


# ─── Delete Invitation Record ────────────────────────────────────────────────


@router.delete("/{invitation_id}", response_model=MessageResponse)
def delete_invitation(
    invitation_id: int,
    db: Session = Depends(get_db),
    company=Depends(get_current_company),
):
    """Permanently delete an invitation record."""
    invitation = db.query(Invitation).filter(Invitation.id == invitation_id).first()
    if not invitation:
        raise HTTPException(status_code=404, detail="Invitation not found.")

    if invitation.invited_by_type == InvitedByType.company and invitation.invited_by_id != company.id:
        raise HTTPException(status_code=403, detail="Access denied.")
    if invitation.invited_by_type == InvitedByType.employee:
        inviter_emp = db.query(Employee).filter(Employee.id == invitation.invited_by_id).first()
        if not inviter_emp or inviter_emp.company_id != company.id:
            raise HTTPException(status_code=403, detail="Access denied.")

    db.delete(invitation)
    db.commit()

    logger.info("Invitation %s deleted", invitation_id)
    return {"message": "Invitation record deleted."}


# ─── Verify, Accept, Reject (Public / Token-based) ──────────────────────────


@router.get("/verify/{token}", response_model=VerifyInvitationResponse)
def verify_invitation(token: str, db: Session = Depends(get_db)):
    invitation = db.query(Invitation).filter(Invitation.token == token).first()
    if not invitation:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Invalid invitation token."
        )

    if invitation.status != InvitationStatus.pending:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Invitation has already been {invitation.status.value}."
        )

    now = datetime.now(timezone.utc)
    if invitation.token_expires_at < now:
        invitation.status = InvitationStatus.expired
        db.commit()
        raise HTTPException(
            status_code=status.HTTP_410_GONE,
            detail="Invitation has expired."
        )

    # Get company name
    company_name = None
    if invitation.invited_by_type == InvitedByType.company:
        company = db.query(Company).filter(Company.id == invitation.invited_by_id).first()
        company_name = company.name if company else None
    elif invitation.invited_by_type == InvitedByType.employee:
        inviter = db.query(Employee).filter(Employee.id == invitation.invited_by_id).first()
        if inviter:
            company = db.query(Company).filter(Company.id == inviter.company_id).first()
            company_name = company.name if company else None

    existing_user = db.query(Employee).filter(Employee.email == invitation.email).first()
    account_exists = existing_user is not None

    return {
        "email": invitation.email,
        "role_offered": invitation.role_offered,
        "account_exists": account_exists,
        "company_name": company_name,
        "expires_at": invitation.token_expires_at,
        "status": invitation.status.value,
    }


@router.post("/accept", response_model=MessageResponse)
def accept_invitation(payload: AcceptInvitationRequest, db: Session = Depends(get_db)):
    invitation = db.query(Invitation).filter(Invitation.token == payload.token).first()
    if not invitation:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Invalid invitation token."
        )

    if invitation.status != InvitationStatus.pending:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Invitation has already been {invitation.status.value}."
        )

    now = datetime.now(timezone.utc)
    if invitation.token_expires_at < now:
        invitation.status = InvitationStatus.expired
        db.commit()
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Invitation token has expired."
        )

    # Find the existing employee
    employee = db.query(Employee).filter(Employee.email == invitation.email).first()
    if not employee:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="No account exists for this email. Please register first."
        )

    # Update employee role and company details
    company_id = None
    invited_by_id = None

    if invitation.invited_by_type == InvitedByType.company:
        company_id = invitation.invited_by_id
    elif invitation.invited_by_type == InvitedByType.employee:
        inviter = db.query(Employee).filter(Employee.id == invitation.invited_by_id).first()
        if not inviter:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Inviting employee no longer exists."
            )
        company_id = inviter.company_id
        invited_by_id = inviter.id

    employee.company_id = company_id
    employee.invited_by_id = invited_by_id
    employee.manager_id = invitation.manager_id
    employee.role = EmployeeRole(invitation.role_offered.value)
    employee.is_verified = True

    invitation.status = InvitationStatus.accepted
    invitation.accepted_at = now

    if invitation.invited_by_type == InvitedByType.employee:
        inviter = db.query(Employee).filter(Employee.id == invitation.invited_by_id).first()
        if inviter:
            create_notification(db, inviter, "Invitation accepted", f"{employee.email} accepted your invitation.", "invitation_accepted")
    create_notification(db, employee, "Invitation accepted", "Your organization invitation was accepted.", "invitation_accepted")
    db.commit()

    return {"message": "Invitation accepted successfully. Account linked to organization."}


@router.post("/reject", response_model=MessageResponse)
def reject_invitation(payload: RejectInvitationRequest, db: Session = Depends(get_db)):
    invitation = db.query(Invitation).filter(Invitation.token == payload.token).first()
    if not invitation:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Invalid invitation token."
        )

    if invitation.status != InvitationStatus.pending:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Invitation has already been {invitation.status.value}."
        )

    now = datetime.now(timezone.utc)
    invitation.status = InvitationStatus.rejected
    invitation.rejected_at = now

    if invitation.invited_by_type == InvitedByType.employee:
        inviter = db.query(Employee).filter(Employee.id == invitation.invited_by_id).first()
        if inviter:
            create_notification(db, inviter, "Invitation rejected", f"{invitation.email} rejected your invitation.", "invitation_rejected")
    db.commit()

    return {"message": "Invitation rejected successfully."}
