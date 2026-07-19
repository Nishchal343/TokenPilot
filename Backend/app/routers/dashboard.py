from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.core.dependencies import get_current_company, get_current_employee, get_current_manager
from app.models.company import Company
from app.models.employee import Employee
from app.models.enums import EmployeeRole, InvitationStatus
from app.models.invitation import Invitation
from app.models.token_budget import TokenBudget
from app.services.analytics_service import descendants, token_stats
from app.services.token_usage_service import get_or_create_budget
from app.core.dependencies import get_current_token_payload

router = APIRouter(prefix="/dashboard", tags=["Dashboards"])


def employee_summary(employee, company_name):
    return {
        "employee_name": employee.name,
        "role": employee.role,
        "company_name": company_name,
        "reporting_manager": employee.manager.name if employee.manager else None,
        "joined_at": employee.created_at,
    }


@router.get("/company")
def company_dashboard(db: Session = Depends(get_db), company=Depends(get_current_company)):
    employees = db.query(Employee).filter(Employee.company_id == company.id).all()
    budgets = db.query(TokenBudget).filter(TokenBudget.company_id == company.id).all()
    invites = db.query(Invitation).filter(Invitation.invited_by_type == "company", Invitation.invited_by_id == company.id).all()
    stats = token_stats(budgets)
    return {
        "company_name": company.name,
        "total_team_leads": sum(item.role == EmployeeRole.manager for item in employees),
        "total_employees": sum(item.role == EmployeeRole.employee for item in employees),
        "total_users": len(employees),
        "active_users": sum(item.is_verified for item in employees),
        "pending_invitations": sum(item.status == InvitationStatus.pending for item in invites),
        "accepted_invitations": sum(item.status == InvitationStatus.accepted for item in invites),
        "rejected_invitations": sum(item.status == InvitationStatus.rejected for item in invites),
        "top_level_team_leads": sum(item.role == EmployeeRole.manager and item.manager_id is None for item in employees),
        **stats,
        "top_token_consumers": [{"employee_id": item.employee_id, "used_tokens": item.used_tokens} for item in sorted(budgets, key=lambda x: x.used_tokens, reverse=True)[:10]],
        "latest_joined_employees": [{"id": item.id, "name": item.name, "email": item.email} for item in sorted(employees, key=lambda x: x.created_at or 0, reverse=True)[:10]],
        "recent_invitations": [{"email": item.email, "status": item.status, "created_at": item.created_at} for item in sorted(invites, key=lambda x: x.created_at or 0, reverse=True)[:10]],
    }


@router.get("/team-lead")
def team_dashboard(db: Session = Depends(get_db), manager=Depends(get_current_manager)):
    people = [manager] + descendants(manager)
    ids = {person.id for person in people}
    budgets = db.query(TokenBudget).filter(TokenBudget.employee_id.in_(ids)).all()
    invites = db.query(Invitation).filter(Invitation.invited_by_type == "employee", Invitation.invited_by_id.in_(ids)).all()
    stats = token_stats(budgets)
    return {
        "manager_name": manager.name,
        "reporting_manager": manager.manager.name if manager.manager else None,
        "direct_team_leads": sum(item.role == EmployeeRole.manager for item in manager.subordinates),
        "direct_team_members": sum(item.role == EmployeeRole.employee for item in manager.subordinates),
        "total_people_under_manager": len(people) - 1,
        "active_team_members": sum(item.is_verified for item in people if item.id != manager.id),
        "pending_invitations_sent": sum(item.status == InvitationStatus.pending for item in invites),
        "accepted_invitations_sent": sum(item.status == InvitationStatus.accepted for item in invites),
        "rejected_invitations_sent": sum(item.status == InvitationStatus.rejected for item in invites),
        "team_monthly_budget": stats["total_monthly_token_budget"],
        "team_tokens_used": stats["total_tokens_used"],
        "team_tokens_remaining": stats["total_tokens_remaining"],
        "estimated_team_cost": stats["estimated_ai_cost"],
        "total_team_requests": stats["total_ai_requests"],
        "most_used_model": stats["most_used_ai_model"],
        # TokenBudget currently has no cache-savings metric; keep this explicit
        # so the UI does not present fabricated analytics.
        "cache_savings": None,
        "latest_team_members": [{"id": item.id, "name": item.name, "email": item.email} for item in people if item.id != manager.id],
    }


@router.get("/employee")
def employee_dashboard(db: Session = Depends(get_db), employee=Depends(get_current_employee)):
    company = db.query(Company).filter(Company.id == employee.company_id).first()
    budget = get_or_create_budget(db, employee)
    db.commit()
    return {
        **employee_summary(employee, company.name if company else None),
        "monthly_budget": budget.monthly_limit,
        "used_tokens": budget.used_tokens,
        "remaining_tokens": budget.remaining_tokens,
        "total_requests": budget.total_requests,
        "estimated_cost": budget.estimated_cost,
        "last_used_at": budget.last_used_at,
        "model_usage": {"GPT requests": budget.gpt_requests, "Gemini requests": budget.gemini_requests, "Claude requests": budget.claude_requests, "Other model requests": budget.other_requests},
    }
