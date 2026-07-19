from datetime import datetime
from typing import Optional

from pydantic import BaseModel, Field
from app.models.enums import EmployeeRole


class RoleChangeRequest(BaseModel):
    manager_id: int | None = None


class UpdateMemberRoleRequest(BaseModel):
    role: EmployeeRole
    manager_id: int | None = None


class OrganizationEmployeeResponse(BaseModel):
    id: int
    name: str
    email: str
    role: EmployeeRole | None
    company_id: int | None
    manager_id: int | None
    is_verified: bool

    model_config = {"from_attributes": True}


class OrganizationTreeNode(OrganizationEmployeeResponse):
    children: list["OrganizationTreeNode"] = Field(default_factory=list)


class OrganizationMemberResponse(BaseModel):
    id: int
    name: str
    email: str
    role: EmployeeRole | None
    is_verified: bool
    avatar_url: Optional[str] = None
    department: Optional[str] = None
    designation: Optional[str] = None
    created_at: Optional[datetime] = None
    last_login_at: Optional[datetime] = None
    manager_id: Optional[int] = None
    manager_name: Optional[str] = None

    model_config = {"from_attributes": True}
