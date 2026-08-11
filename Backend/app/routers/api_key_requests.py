from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.core.dependencies import get_current_company, get_current_assigned_team_member, get_current_employee, get_current_manager
from app.models.api_key_request import APIKey, APIKeyRequest
from app.models.enums import APIKeyRequestStatus
from app.schemas.api_key_request import (
    APIKeyCreate,
    APIKeyRequestAction,
    APIKeyRequestCreate,
    APIKeyRequestResponse,
    APIKeyResponse,
    CompanyAPIKeyAction,
)
from app.services.api_key_workflow import (
    add_audit,
    create_company_api_key,
    create_request,
    ensure_rejection_reason,
    notify_company,
    notify_employee,
    request_response,
)

router = APIRouter(prefix="/api", tags=["AI API Key Approval"])


@router.post("/requests", response_model=APIKeyRequestResponse, status_code=201)
def submit_request(payload: APIKeyRequestCreate, db: Session = Depends(get_db), employee=Depends(get_current_employee)):
    request = create_request(db, employee, payload)
    db.commit()
    db.refresh(request)
    return request_response(request)


@router.get("/requests/my", response_model=list[APIKeyRequestResponse])
def my_requests(db: Session = Depends(get_db), employee=Depends(get_current_employee)):
    requests = db.query(APIKeyRequest).filter(APIKeyRequest.employee_id == employee.id).order_by(APIKeyRequest.created_at.desc()).all()
    return [request_response(item) for item in requests]


@router.get("/teamleader/requests", response_model=list[APIKeyRequestResponse])
def teamleader_requests(db: Session = Depends(get_db), manager=Depends(get_current_manager)):
    requests = db.query(APIKeyRequest).filter(
        APIKeyRequest.team_leader_id == manager.id,
        APIKeyRequest.status == APIKeyRequestStatus.PENDING_TEAM_LEADER.value,
    ).order_by(APIKeyRequest.created_at.asc()).all()
    return [request_response(item) for item in requests]


@router.patch("/teamleader/requests/{request_id}", response_model=APIKeyRequestResponse)
def act_on_teamleader_request(request_id: int, payload: APIKeyRequestAction, db: Session = Depends(get_db), manager=Depends(get_current_manager)):
    request = db.query(APIKeyRequest).filter(
        APIKeyRequest.id == request_id,
        APIKeyRequest.team_leader_id == manager.id,
        APIKeyRequest.company_id == manager.company_id,
    ).first()
    if not request:
        raise HTTPException(status_code=404, detail="API key request not found in your team.")
    if request.status != APIKeyRequestStatus.PENDING_TEAM_LEADER.value:
        raise HTTPException(status_code=409, detail="This request is no longer pending team leader approval.")

    if payload.action == "reject":
        ensure_rejection_reason(payload.reason)
        request.status = APIKeyRequestStatus.REJECTED_BY_TEAM_LEADER.value
        request.rejection_reason = payload.reason.strip()
        add_audit(db, request, "team_leader", manager.id, "REJECTED", reason=request.rejection_reason)
        notify_employee(db, request.employee, "AI API key request rejected", request.rejection_reason, "api_key_request")
    else:
        budget = payload.modified_budget or request.requested_budget
        request.leader_modified_budget = budget
        request.status = APIKeyRequestStatus.PENDING_COMPANY.value
        add_audit(db, request, "team_leader", manager.id, "APPROVED", old_budget=request.requested_budget, new_budget=budget, reason=payload.reason)
        notify_employee(db, request.employee, "AI API key request advanced", "Your request was approved by your team leader and is pending company approval.", "api_key_request")
        notify_company(request.company, "AI API key request needs company approval", f"{request.employee.name}'s request for {request.requested_model} is ready for review.")

    db.commit()
    db.refresh(request)
    return request_response(request)


@router.get("/company/api-key-requests", response_model=list[APIKeyRequestResponse])
def company_api_key_requests(db: Session = Depends(get_db), company=Depends(get_current_company)):
    requests = db.query(APIKeyRequest).filter(
        APIKeyRequest.company_id == company.id,
        APIKeyRequest.status.in_([
            APIKeyRequestStatus.PENDING_COMPANY.value,
            APIKeyRequestStatus.APPROVED.value,
            APIKeyRequestStatus.REJECTED.value,
        ]),
    ).order_by(APIKeyRequest.created_at.desc()).all()
    return [request_response(item) for item in requests]


@router.patch("/company/api-key-requests/{request_id}", response_model=APIKeyRequestResponse)
def act_on_company_request(request_id: int, payload: CompanyAPIKeyAction, db: Session = Depends(get_db), company=Depends(get_current_company)):
    request = db.query(APIKeyRequest).filter(APIKeyRequest.id == request_id, APIKeyRequest.company_id == company.id).first()
    if not request:
        raise HTTPException(status_code=404, detail="API key request not found.")
    if payload.action == "reject":
        if request.status != APIKeyRequestStatus.PENDING_COMPANY.value:
            raise HTTPException(status_code=409, detail="Only pending company requests can be rejected.")
        ensure_rejection_reason(payload.reason)
        request.status = APIKeyRequestStatus.REJECTED.value
        request.rejection_reason = payload.reason.strip()
        add_audit(db, request, "company", company.id, "REJECTED", reason=request.rejection_reason)
        notify_employee(db, request.employee, "AI API key request rejected", request.rejection_reason, "api_key_request")
        notify_employee(db, request.team_leader, "Team member API request rejected", f"The company rejected {request.employee.name}'s API key request.", "api_key_request")
    else:
        if not payload.provider or not payload.api_key or not payload.final_budget:
            raise HTTPException(status_code=400, detail="Provider, API key, and final budget are required for approval.")
        create_company_api_key(db, company, request, payload.provider, payload.api_key.get_secret_value(), payload.final_budget, company.id)

    db.commit()
    db.refresh(request)
    return request_response(request)


@router.post("/company/api-keys", response_model=APIKeyResponse, status_code=201)
def create_api_key(payload: APIKeyCreate, db: Session = Depends(get_db), company=Depends(get_current_company)):
    request = db.query(APIKeyRequest).filter(APIKeyRequest.id == payload.request_id, APIKeyRequest.company_id == company.id).first()
    if not request:
        raise HTTPException(status_code=404, detail="API key request not found.")
    api_key = create_company_api_key(db, company, request, payload.provider, payload.api_key.get_secret_value(), payload.final_budget, company.id)
    db.commit()
    db.refresh(api_key)
    return api_key


@router.get("/company/api-keys", response_model=list[APIKeyResponse])
def company_api_keys(db: Session = Depends(get_db), company=Depends(get_current_company)):
    return db.query(APIKey).filter(APIKey.company_id == company.id).order_by(APIKey.created_at.desc()).all()
