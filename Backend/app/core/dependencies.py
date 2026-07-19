from fastapi import Depends, HTTPException, status
from fastapi.security import OAuth2PasswordBearer
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.core.security import decode_access_token
from app.models.company import Company
from app.models.employee import Employee
from app.models.enums import EmployeeRole

oauth2_scheme = OAuth2PasswordBearer(
    tokenUrl="/auth/employee/login"
)


def get_current_token_payload(token: str = Depends(oauth2_scheme)) -> dict:
    payload = decode_access_token(token)
    if not payload:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Could not validate credentials",
            headers={"WWW-Authenticate": "Bearer"},
        )
    return payload


def get_current_company(
    db: Session = Depends(get_db),
    payload: dict = Depends(get_current_token_payload)
) -> Company:
    if payload.get("type") != "company":
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Access denied. Company account required.",
        )
    
    company_id = payload.get("company_id")
    if not company_id:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid token payload",
        )
        
    company = db.query(Company).filter(Company.id == company_id).first()
    if not company:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Company not found",
        )
    if not company.is_verified:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Company email is not verified.",
        )
    return company


def get_current_employee(
    db: Session = Depends(get_db),
    payload: dict = Depends(get_current_token_payload)
) -> Employee:
    if payload.get("type") != "employee":
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Access denied. Employee account required.",
        )
        
    employee_id = payload.get("employee_id")
    if not employee_id:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid token payload",
        )
        
    employee = db.query(Employee).filter(Employee.id == employee_id).first()
    if not employee:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Employee not found",
        )
    if not employee.is_verified:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Employee email is not verified.",
        )
    return employee


def get_current_manager(
    employee: Employee = Depends(get_current_employee)
) -> Employee:
    if employee.role != EmployeeRole.manager:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Access denied. Manager (Team Lead) role required.",
        )
    return employee