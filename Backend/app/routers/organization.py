import logging

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.core.dependencies import get_current_company, get_current_manager, get_current_employee, get_current_token_payload
from app.models.company import Company
from app.models.employee import Employee
from app.models.enums import EmployeeRole
from app.services.notification_service import create_notification
from app.schemas.auth import MessageResponse
from app.schemas.organization import (
    OrganizationEmployeeResponse,
    OrganizationMemberResponse,
    OrganizationTreeNode,
    RoleChangeRequest,
    UpdateMemberRoleRequest,
)

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/organization", tags=["Organization"])


def subtree(root: Employee):
    result = []
    stack = [root]
    while stack:
        current = stack.pop()
        result.extend(current.subordinates)
        stack.extend(current.subordinates)
    return result


def tree_node(employee: Employee):
    return {
        "id": employee.id,
        "name": employee.name,
        "email": employee.email,
        "role": employee.role,
        "company_id": employee.company_id,
        "manager_id": employee.manager_id,
        "is_verified": employee.is_verified,
        "children": [tree_node(child) for child in employee.subordinates],
    }


def ensure_manager_target(db: Session, employee: Employee, manager_id: int | None):
    if manager_id is None:
        return None
    manager = db.query(Employee).filter(
        Employee.id == manager_id,
        Employee.company_id == employee.company_id,
        Employee.role == EmployeeRole.manager,
    ).first()
    if not manager or manager.id == employee.id:
        raise HTTPException(status_code=400, detail="manager_id must reference another manager in the company.")
    if manager.id in {item.id for item in subtree(employee)}:
        raise HTTPException(status_code=400, detail="An employee cannot report to a subordinate.")
    return manager


def member_response(db: Session, emp: Employee) -> OrganizationMemberResponse:
    manager_name = None
    if emp.manager_id:
        manager = db.query(Employee).filter(Employee.id == emp.manager_id).first()
        manager_name = manager.name if manager else None
    return OrganizationMemberResponse(
        id=emp.id,
        name=emp.name,
        email=emp.email,
        role=emp.role,
        is_verified=emp.is_verified,
        avatar_url=emp.avatar_url,
        department=emp.department,
        designation=emp.designation,
        created_at=emp.created_at,
        last_login_at=emp.last_login_at,
        manager_id=emp.manager_id,
        manager_name=manager_name,
    )


# ─── Members Management (Company Admin Only) ────────────────────────────────


@router.get("/members", response_model=list[OrganizationMemberResponse])
def list_members(db: Session = Depends(get_db), company=Depends(get_current_company)):
    """List all active company members with manager names."""
    employees = (
        db.query(Employee)
        .filter(Employee.company_id == company.id)
        .order_by(Employee.name)
        .all()
    )

    result = []
    for emp in employees:
        manager_name = None
        if emp.manager_id:
            mgr = db.query(Employee).filter(Employee.id == emp.manager_id).first()
            if mgr:
                manager_name = mgr.name

        result.append(OrganizationMemberResponse(
            id=emp.id,
            name=emp.name,
            email=emp.email,
            role=emp.role,
            is_verified=emp.is_verified,
            avatar_url=emp.avatar_url,
            department=emp.department,
            designation=emp.designation,
            created_at=emp.created_at,
            last_login_at=emp.last_login_at,
            manager_id=emp.manager_id,
            manager_name=manager_name,
        ))

    return result


@router.get("/members/{member_id}", response_model=OrganizationMemberResponse)
def get_member_detail(member_id: int, db: Session = Depends(get_db), company=Depends(get_current_company)):
    """Get detailed info for a single member."""
    emp = db.query(Employee).filter(
        Employee.id == member_id,
        Employee.company_id == company.id,
    ).first()
    if not emp:
        raise HTTPException(status_code=404, detail="Member not found in organization.")

    manager_name = None
    if emp.manager_id:
        mgr = db.query(Employee).filter(Employee.id == emp.manager_id).first()
        if mgr:
            manager_name = mgr.name

    return OrganizationMemberResponse(
        id=emp.id,
        name=emp.name,
        email=emp.email,
        role=emp.role,
        is_verified=emp.is_verified,
        avatar_url=emp.avatar_url,
        department=emp.department,
        designation=emp.designation,
        created_at=emp.created_at,
        last_login_at=emp.last_login_at,
        manager_id=emp.manager_id,
        manager_name=manager_name,
    )


@router.get("/team-members", response_model=list[OrganizationMemberResponse])
def list_team_members(
    db: Session = Depends(get_db),
    manager=Depends(get_current_manager),
):
    """Return only employees in the manager's assigned subtree."""
    return [member_response(db, employee) for employee in subtree(manager) if employee.role == EmployeeRole.employee]


@router.get("/team-members/{member_id}", response_model=OrganizationMemberResponse)
def get_team_member(member_id: int, db: Session = Depends(get_db), manager=Depends(get_current_manager)):
    employee = next((item for item in subtree(manager) if item.id == member_id and item.role == EmployeeRole.employee), None)
    if not employee:
        raise HTTPException(status_code=404, detail="Employee is not in your assigned team.")
    return member_response(db, employee)


@router.delete("/team-members/{member_id}", response_model=MessageResponse)
def remove_team_member(member_id: int, db: Session = Depends(get_db), manager=Depends(get_current_manager)):
    employee = next((item for item in subtree(manager) if item.id == member_id and item.role == EmployeeRole.employee), None)
    if not employee:
        raise HTTPException(status_code=404, detail="Employee is not in your assigned team.")
    employee.company_id = None
    employee.manager_id = None
    employee.invited_by_id = None
    employee.role = None
    db.commit()
    return {"message": f"{employee.name} has been removed from your team."}


@router.patch("/members/{member_id}/role", response_model=MessageResponse)
def update_member_role(
    member_id: int,
    body: UpdateMemberRoleRequest,
    db: Session = Depends(get_db),
    company=Depends(get_current_company),
):
    """Update a member's role. Company admin only."""
    employee = db.query(Employee).filter(
        Employee.id == member_id,
        Employee.company_id == company.id,
    ).first()
    if not employee:
        raise HTTPException(status_code=404, detail="Member not found in organization.")

    old_role = employee.role
    employee.role = body.role

    # Handle manager assignment
    if body.role == EmployeeRole.manager:
        if body.manager_id is not None:
            manager = ensure_manager_target(db, employee, body.manager_id)
            employee.manager_id = manager.id if manager else None
        # If promoting to manager, reassign subordinates that would create cycles
    elif body.role == EmployeeRole.employee:
        # When demoting: reassign all direct subordinates to this employee's manager
        for sub in employee.subordinates:
            sub.manager_id = employee.manager_id
        if body.manager_id is not None:
            manager = ensure_manager_target(db, employee, body.manager_id)
            employee.manager_id = manager.id if manager else None

    role_label = "Manager" if body.role == EmployeeRole.manager else "Employee"
    create_notification(
        db, employee,
        "Role updated",
        f"Your role has been changed to {role_label}.",
        "role_change",
    )
    db.commit()

    logger.info("Member %s role changed from %s to %s", member_id, old_role, body.role)
    return {"message": f"Member role updated to {role_label} successfully."}


@router.delete("/members/{member_id}", response_model=MessageResponse)
def remove_member(
    member_id: int,
    db: Session = Depends(get_db),
    company=Depends(get_current_company),
    payload: dict = Depends(get_current_token_payload),
):
    """Remove a member from the organization. Company admin only. Cannot remove self."""
    # Prevent company admin from removing themselves
    if payload.get("type") == "company":
        # Company admins cannot be removed via this endpoint (they are not employees)
        pass

    employee = db.query(Employee).filter(
        Employee.id == member_id,
        Employee.company_id == company.id,
    ).first()
    if not employee:
        raise HTTPException(status_code=404, detail="Member not found in organization.")

    # Reassign subordinates to removed member's manager
    for sub in employee.subordinates:
        sub.manager_id = employee.manager_id

    # Detach from organization (soft removal)
    employee.company_id = None
    employee.manager_id = None
    employee.invited_by_id = None
    employee.role = None

    db.commit()
    logger.info("Member %s removed from company %s", member_id, company.id)
    return {"message": f"{employee.name} has been removed from the organization."}


# ─── Existing Endpoints (preserved) ─────────────────────────────────────────


@router.get("/employees", response_model=list[OrganizationEmployeeResponse])
def list_organization(db: Session = Depends(get_db), company=Depends(get_current_company)):
    return db.query(Employee).filter(Employee.company_id == company.id).all()


@router.get("/my-subtree", response_model=list[OrganizationEmployeeResponse])
def list_my_subtree(db: Session = Depends(get_db), manager=Depends(get_current_manager)):
    return subtree(manager)


@router.get("/tree")
def organization_tree(db: Session = Depends(get_db), payload: dict = Depends(get_current_token_payload)):
    if payload.get("type") == "company":
        company = db.query(Company).filter(Company.id == payload.get("company_id"), Company.is_verified.is_(True)).first()
        if not company:
            raise HTTPException(status_code=403, detail="Verified company account required.")
        employees = db.query(Employee).filter(Employee.company_id == company.id, Employee.manager_id.is_(None)).all()
        return [tree_node(employee) for employee in employees]
    employee = db.query(Employee).filter(Employee.id == payload.get("employee_id"), Employee.is_verified.is_(True)).first()
    if not employee:
        raise HTTPException(status_code=403, detail="Verified employee account required.")
    if employee.role == EmployeeRole.employee:
        return [tree_node(employee)]
    return [tree_node(employee)]


@router.get("/me")
def organization_me(db: Session = Depends(get_db), employee=Depends(get_current_employee)):
    company = db.query(Company).filter(Company.id == employee.company_id).first()
    return {
        "current_employee": tree_node(employee),
        "reporting_manager": tree_node(employee.manager) if employee.manager else None,
        "direct_reports": [tree_node(item) for item in employee.subordinates],
        "company": {"id": company.id, "name": company.name} if company else None,
    }


@router.get("/subordinates", response_model=list[OrganizationEmployeeResponse])
def organization_subordinates(db: Session = Depends(get_db), payload: dict = Depends(get_current_token_payload)):
    if payload.get("type") == "company":
        company = db.query(Company).filter(Company.id == payload.get("company_id"), Company.is_verified.is_(True)).first()
        if not company:
            raise HTTPException(status_code=403, detail="Verified company account required.")
        return db.query(Employee).filter(Employee.company_id == company.id).all()
    employee = db.query(Employee).filter(Employee.id == payload.get("employee_id"), Employee.is_verified.is_(True)).first()
    if not employee or employee.role != EmployeeRole.manager:
        raise HTTPException(status_code=403, detail="Only managers can view subordinates.")
    return subtree(employee)


@router.post("/employees/{employee_id}/promote", response_model=MessageResponse)
def promote(employee_id: int, payload: RoleChangeRequest, db: Session = Depends(get_db), company=Depends(get_current_company)):
    employee = db.query(Employee).filter(Employee.id == employee_id, Employee.company_id == company.id).first()
    if not employee:
        raise HTTPException(status_code=404, detail="Employee not found in organization.")
    manager = ensure_manager_target(db, employee, payload.manager_id)
    employee.role = EmployeeRole.manager
    employee.manager_id = manager.id if manager else None
    create_notification(db, employee, "Promotion", "You have been promoted to manager.", "promotion")
    db.commit()
    return {"message": "Employee promoted successfully."}


@router.post("/employees/{employee_id}/demote", response_model=MessageResponse)
def demote(employee_id: int, db: Session = Depends(get_db), company=Depends(get_current_company)):
    employee = db.query(Employee).filter(Employee.id == employee_id, Employee.company_id == company.id).first()
    if not employee:
        raise HTTPException(status_code=404, detail="Employee not found in organization.")
    employee.role = EmployeeRole.employee
    create_notification(db, employee, "Demotion", "You have been changed to the employee role.", "demotion")
    db.commit()
    return {"message": "Manager demoted successfully."}


@router.patch("/employees/{employee_id}/manager", response_model=MessageResponse)
def change_manager(employee_id: int, payload: RoleChangeRequest, db: Session = Depends(get_db), company=Depends(get_current_company)):
    employee = db.query(Employee).filter(Employee.id == employee_id, Employee.company_id == company.id).first()
    if not employee:
        raise HTTPException(status_code=404, detail="Employee not found in organization.")
    manager = ensure_manager_target(db, employee, payload.manager_id)
    employee.manager_id = manager.id if manager else None
    message = f"Your reporting manager is now {manager.name}." if manager else "You now report directly to the company."
    create_notification(db, employee, "Reporting manager changed", message, "reporting_manager_changed")
    db.commit()
    return {"message": "Reporting manager changed successfully."}
