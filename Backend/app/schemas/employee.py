from datetime import datetime

from pydantic import BaseModel, EmailStr, Field

from app.models.enums import EmployeeRole


class EmployeeRegisterRequest(BaseModel):
    name: str = Field(..., min_length=2, max_length=255)
    email: EmailStr
    password: str = Field(..., min_length=8)
    confirm_password: str


class EmployeeVerifyOTPRequest(BaseModel):
    email: EmailStr
    otp: str = Field(..., min_length=6, max_length=6)


class EmployeeLoginRequest(BaseModel):
    email: EmailStr
    password: str


class EmployeeForgotPasswordRequest(BaseModel):
    email: EmailStr


class EmployeeResetPasswordRequest(BaseModel):
    email: EmailStr
    otp: str = Field(..., min_length=6, max_length=6)
    new_password: str = Field(..., min_length=8)
    confirm_password: str


class EmployeeResponse(BaseModel):
    id: int
    name: str
    email: EmailStr
    is_verified: bool
    role: EmployeeRole | None
    company_id: int | None
    invited_by_id: int | None
    created_at: datetime

    model_config = {
        "from_attributes": True
    }