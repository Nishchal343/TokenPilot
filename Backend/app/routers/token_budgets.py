from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.core.dependencies import get_current_company, get_current_employee, get_current_manager
from app.models.employee import Employee
from app.models.enums import EmployeeRole
from app.models.token_budget import TokenBudget
from app.schemas.auth import MessageResponse
from app.schemas.token_budget import TokenBudgetCreate, TokenBudgetResponse, TokenBudgetUpdate
from app.services.analytics_service import descendants
from app.services.token_usage_service import get_or_create_budget, reset_budget

router = APIRouter(prefix="/token-budgets", tags=["Token Budgets"])


@router.post("", response_model=TokenBudgetResponse)
def assign_budget(payload: TokenBudgetCreate, db: Session = Depends(get_db), company=Depends(get_current_company)):
    employee = db.query(Employee).filter(Employee.id == payload.employee_id, Employee.company_id == company.id).first()
    if not employee:
        raise HTTPException(status_code=404, detail="Employee not found in organization.")
    budget = get_or_create_budget(db, employee)
    budget.monthly_limit = payload.monthly_limit
    budget.remaining_tokens = max(payload.monthly_limit - budget.used_tokens, 0)
    db.commit()
    db.refresh(budget)
    return budget


@router.patch("/{employee_id}", response_model=TokenBudgetResponse)
def update_budget(employee_id: int, payload: TokenBudgetUpdate, db: Session = Depends(get_db), company=Depends(get_current_company)):
    employee = db.query(Employee).filter(Employee.id == employee_id, Employee.company_id == company.id).first()
    if not employee:
        raise HTTPException(status_code=404, detail="Employee not found in organization.")
    budget = get_or_create_budget(db, employee)
    budget.monthly_limit = payload.monthly_limit
    budget.remaining_tokens = max(payload.monthly_limit - budget.used_tokens, 0)
    db.commit()
    db.refresh(budget)
    return budget


@router.post("/reset", response_model=MessageResponse)
def reset_budgets(db: Session = Depends(get_db), company=Depends(get_current_company)):
    budgets = db.query(TokenBudget).filter(TokenBudget.company_id == company.id).all()
    for budget in budgets:
        reset_budget(budget)
    db.commit()
    return {"message": "Monthly budgets reset successfully."}


@router.get("/company", response_model=list[TokenBudgetResponse])
def company_budgets(db: Session = Depends(get_db), company=Depends(get_current_company)):
    return db.query(TokenBudget).filter(TokenBudget.company_id == company.id).all()


@router.get("/team", response_model=list[TokenBudgetResponse])
def team_budgets(db: Session = Depends(get_db), manager=Depends(get_current_manager)):
    ids = [employee.id for employee in descendants(manager)] + [manager.id]
    return db.query(TokenBudget).filter(TokenBudget.employee_id.in_(ids)).all()


@router.patch("/team/{employee_id}", response_model=TokenBudgetResponse)
def update_team_budget(employee_id: int, payload: TokenBudgetUpdate, db: Session = Depends(get_db), manager=Depends(get_current_manager)):
    team_ids = {employee.id for employee in descendants(manager) if employee.role == EmployeeRole.employee}
    if employee_id not in team_ids:
        raise HTTPException(status_code=404, detail="Employee is not in your assigned team.")

    manager_budget = get_or_create_budget(db, manager)
    allocated_elsewhere = sum(
        (budget.monthly_limit or 0)
        for budget in db.query(TokenBudget).filter(TokenBudget.employee_id.in_(team_ids - {employee_id})).all()
    )
    if allocated_elsewhere + payload.monthly_limit > manager_budget.monthly_limit:
        raise HTTPException(status_code=400, detail="This allocation exceeds your team budget.")

    employee = db.query(Employee).filter(Employee.id == employee_id).first()
    budget = get_or_create_budget(db, employee)
    budget.monthly_limit = payload.monthly_limit
    budget.remaining_tokens = max(payload.monthly_limit - budget.used_tokens, 0)
    db.commit()
    db.refresh(budget)
    return budget


@router.get("/me", response_model=TokenBudgetResponse)
def my_budget(db: Session = Depends(get_db), employee=Depends(get_current_employee)):
    budget = get_or_create_budget(db, employee)
    db.commit()
    db.refresh(budget)
    return budget
