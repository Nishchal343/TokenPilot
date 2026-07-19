from datetime import datetime
from typing import Optional
from pydantic import BaseModel


class SecurityLogEntry(BaseModel):
    event_type: str
    ip_address: Optional[str] = None
    created_at: datetime

    model_config = {"from_attributes": True}


class SecurityInfoResponse(BaseModel):
    email: str
    is_verified: bool
    role: str
    last_login_at: Optional[datetime] = None
    created_at: datetime
    recent_logins: list[SecurityLogEntry] = []
