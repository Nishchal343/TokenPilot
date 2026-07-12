from pydantic import BaseModel, EmailStr, Field
from datetime import datetime


class CompanyRegisterRequest(BaseModel):
    name: str = Field(..., min_length=2, max_length=255)
    email: EmailStr
    password: str = Field(..., min_length=8)
    confirm_password: str


class CompanyVerifyOTPRequest(BaseModel):
    email: EmailStr
    otp: str = Field(..., min_length=6, max_length=6)


class CompanyLoginRequest(BaseModel):
    email: EmailStr
    password: str


class CompanyForgotPasswordRequest(BaseModel):
    email: EmailStr


class CompanyResetPasswordRequest(BaseModel):
    email: EmailStr
    otp: str = Field(..., min_length=6, max_length=6)
    new_password: str = Field(..., min_length=8)
    confirm_password: str


class CompanyResponse(BaseModel):
    id: int
    name: str
    email: EmailStr
    is_verified: bool
    created_at: datetime

    model_config = {
        "from_attributes": True
    }