import base64
import hashlib

from cryptography.fernet import Fernet
from fastapi import HTTPException
from sqlalchemy.orm import Session

from app.core.config import settings
from app.models.api_key_request import APIKey, APIKeyAuditLog, APIKeyRequest
from app.models.employee import Employee
from app.models.enums import APIKeyRequestStatus, EmployeeRole
from app.services.email_service import email_service
from app.services.notification_service import create_notification


def _cipher() -> Fernet:
    configured = getattr(settings, "API_KEY_ENCRYPTION_KEY", None)
    key = configured.encode() if configured else base64.urlsafe_b64encode(hashlib.sha256(settings.SECRET_KEY.encode()).digest())
    return Fernet(key)


def encrypt_api_key(value: str) -> str:
    return _cipher().encrypt(value.encode()).decode()


def add_audit(db: Session, request: APIKeyRequest, actor_type: str, actor_id: int, action: str, old_budget=None, new_budget=None, reason=None):
    db.add(APIKeyAuditLog(
        request_id=request.id,
        actor_type=actor_type,
        actor_id=actor_id,
        action=action,
        old_budget=old_budget,
        new_budget=new_budget,
        reason=reason,
    ))


def notify_employee(db: Session, employee: Employee, title: str, message: str, event_type: str):
    create_notification(db, employee, title, message, event_type)


def notify_company(company, title: str, message: str):
    # Company accounts do not have employee notification rows; email is the existing
    # notification channel for company administrators.
    email_service.send_notification_email(company.email, title, message)


def request_response(request: APIKeyRequest) -> dict:
    return {
        "id": request.id,
        "company_id": request.company_id,
        "team_leader_id": request.team_leader_id,
        "employee_id": request.employee_id,
        "employee_name": ('manager' if request.employee_id == request.team_leader_id else 'member') if request.employee else None,
        "team_leader_name": request.team_leader.name if request.team_leader else None,
        "requested_tier": request.requested_tier,
        "requested_provider": request.requested_provider,
        "requested_model": request.requested_model,
        "requested_budget": request.requested_budget,
        "leader_modified_budget": request.leader_modified_budget,
        "company_final_budget": request.company_final_budget,
        "status": request.status,
        "reason": request.reason,
        "rejection_reason": request.rejection_reason,
        "api_key_id": request.api_key_id,
        "created_at": request.created_at,
        "updated_at": request.updated_at,
    }


def ensure_rejection_reason(reason: str | None):
    if not reason or not reason.strip():
        raise HTTPException(status_code=400, detail="A rejection reason is required.")


def create_request(db: Session, employee: Employee, payload) -> APIKeyRequest:
    if not employee.company_id:
        raise HTTPException(status_code=400, detail="Join a company before requesting an AI API key.")

    if employee.role == EmployeeRole.manager:
        request = APIKeyRequest(
            company_id=employee.company_id,
            team_leader_id=employee.id,
            employee_id=employee.id,
            requested_tier=payload.requested_tier,
            requested_provider=payload.requested_provider,
            requested_model=payload.requested_model.strip(),
            requested_budget=payload.requested_budget,
            status=APIKeyRequestStatus.PENDING_COMPANY.value,
            reason=payload.reason.strip(),
        )
        db.add(request)
        db.flush()
        add_audit(db, request, "manager", employee.id, "SUBMITTED", new_budget=payload.requested_budget)
        notify_employee(db, employee, "AI API key request submitted", "Your request is pending company approval.", "api_key_request")
        notify_company(employee.company, "Manager AI API key request needs approval", f"{employee.name} requested access to {request.requested_model}.")
        return request

    if not employee.manager_id:
        raise HTTPException(status_code=400, detail="A team leader must be assigned before requesting an AI API key.")
    leader = db.query(Employee).filter(
        Employee.id == employee.manager_id,
        Employee.company_id == employee.company_id,
        Employee.role == EmployeeRole.manager,
    ).first()
    if not leader:
        raise HTTPException(status_code=400, detail="The assigned team leader could not be found.")

    request = APIKeyRequest(
        company_id=employee.company_id,
        team_leader_id=leader.id,
        employee_id=employee.id,
        requested_tier=payload.requested_tier,
        requested_provider=payload.requested_provider,
        requested_model=payload.requested_model.strip(),
        requested_budget=payload.requested_budget,
        status=APIKeyRequestStatus.PENDING_TEAM_LEADER.value,
        reason=payload.reason.strip(),
    )
    db.add(request)
    db.flush()
    add_audit(db, request, "employee", employee.id, "SUBMITTED", new_budget=payload.requested_budget)
    notify_employee(db, employee, "AI API key request submitted", "Your request is pending team leader approval.", "api_key_request")
    notify_employee(db, leader, "AI API key request needs review", f"{employee.name} requested access to {request.requested_model}.", "api_key_request")
    return request


def create_company_api_key(db: Session, company, request: APIKeyRequest, provider: str, secret: str, final_budget: int, actor_id: int) -> APIKey:
    if request.status != APIKeyRequestStatus.PENDING_COMPANY.value:
        raise HTTPException(status_code=409, detail="Only requests pending company approval can be activated.")
    model = request.requested_model.strip().lower()
    provider_key = provider.strip().lower()
    if provider_key != request.requested_provider.strip().lower():
        raise HTTPException(status_code=400, detail=f"This request is for {request.requested_provider}; activate it with that provider.")
    if model.startswith("gemini") and provider_key != "gemini":
        raise HTTPException(status_code=400, detail="Gemini models require a Gemini provider/API key.")
    if (model.startswith("claude") or model.startswith("anthropic")) and provider_key not in {"claude", "anthropic"}:
        raise HTTPException(status_code=400, detail="Claude models require a Claude/Anthropic provider/API key.")
    api_key = APIKey(
        company_id=company.id,
        employee_id=request.employee_id,
        request_id=request.id,
        provider=provider,
        model=request.requested_model.strip(),
        encrypted_api_key=encrypt_api_key(secret),
        budget_limit=final_budget,
        remaining_budget=final_budget,
        is_active=True,
        created_by=actor_id,
    )
    db.add(api_key)
    db.flush()
    request.company_final_budget = final_budget
    request.api_key_id = api_key.id
    request.status = APIKeyRequestStatus.APPROVED.value
    add_audit(db, request, "company", actor_id, "APPROVED", old_budget=request.leader_modified_budget or request.requested_budget, new_budget=final_budget)
    notify_employee(db, request.employee, "AI API key approved", f"Your {request.requested_model} access is active with a budget of {final_budget:,} tokens.", "api_key_approved")
    notify_employee(db, request.team_leader, "AI API key request completed", f"{request.employee.name}'s request was approved by the company.", "api_key_request")
    return api_key
