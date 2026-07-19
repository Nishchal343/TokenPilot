from typing import Optional
from pydantic import BaseModel


class BugReportRequest(BaseModel):
    category: str
    subject: str
    description: str


class ChangePasswordRequest(BaseModel):
    current_password: str
    new_password: str
    confirm_password: str


class ChangePasswordVerifyRequest(BaseModel):
    otp: str
    new_password: str
    confirm_password: str
