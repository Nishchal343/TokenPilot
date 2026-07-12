from pydantic import BaseModel, EmailStr

from app.models.enums import OfferedRole


class InviteRequest(BaseModel):
    employee_email: EmailStr


class VerifyInvitationResponse(BaseModel):
    email: EmailStr
    role_offered: OfferedRole
    account_exists: bool


class AcceptInvitationRequest(BaseModel):
    token: str


class RejectInvitationRequest(BaseModel):
    token: str