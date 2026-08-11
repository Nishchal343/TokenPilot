from datetime import datetime
from typing import Optional

from pydantic import BaseModel, EmailStr, field_validator, model_validator

from app.models.enums import OfferedRole, InvitationStatus, InvitedByType


class InviteRequest(BaseModel):
    employee_email: EmailStr
    employee_name: Optional[str] = None
    role: OfferedRole | None = None
    manager_id: int | None = None

    @field_validator("role", mode="before")
    @classmethod
    def normalize_role(cls, value):
        # Accept the old employee spelling from existing clients, but always
        # route it through the canonical TEAM_MEMBER policy.
        if isinstance(value, str):
            value = value.lower()
        if value in ("employee", "team_member"):
            return "team_member"
        if value == "manager":
            return "manager"
        return value


class VerifyInvitationResponse(BaseModel):
    email: EmailStr
    role_offered: OfferedRole
    account_exists: bool
    company_name: Optional[str] = None
    expires_at: Optional[datetime] = None
    status: Optional[str] = None


class AcceptInvitationRequest(BaseModel):
    token: str


class RejectInvitationRequest(BaseModel):
    token: str


class InvitationListResponse(BaseModel):
    id: int
    name: Optional[str] = None
    email: str
    role_offered: OfferedRole
    status: InvitationStatus
    token: Optional[str] = None
    token_expires_at: Optional[datetime] = None
    created_at: Optional[datetime] = None
    accepted_at: Optional[datetime] = None
    rejected_at: Optional[datetime] = None
    cancelled_at: Optional[datetime] = None
    invited_by_type: Optional[str] = None

    @model_validator(mode="after")
    def use_role_label_for_display(self):
        self.name = "manager" if self.role_offered == OfferedRole.manager else "member"
        return self
    invited_by_id: Optional[int] = None

    model_config = {"from_attributes": True}


class MyInvitationResponse(BaseModel):
    id: int
    email: EmailStr
    company_name: str
    invited_by_name: str
    invited_by_type: InvitedByType
    role_offered: OfferedRole
    status: InvitationStatus
    token: str
    created_at: Optional[datetime] = None
    token_expires_at: Optional[datetime] = None
