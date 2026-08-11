from typing import Optional
from pydantic import BaseModel


class ProfileResponse(BaseModel):
    # Shared
    name: str
    email: str
    role: str
    company_name: Optional[str] = None
    phone: Optional[str] = None
    address: Optional[str] = None
    city: Optional[str] = None
    state: Optional[str] = None
    country: Optional[str] = None
    postal_code: Optional[str] = None
    avatar_url: Optional[str] = None

    # Employee-only
    department: Optional[str] = None
    designation: Optional[str] = None
    reporting_manager: Optional[str] = None
    manager_id: Optional[int] = None

    # Company-only
    website: Optional[str] = None
    industry: Optional[str] = None
    company_size: Optional[str] = None

    model_config = {"from_attributes": True}


class ProfileUpdateRequest(BaseModel):
    name: Optional[str] = None
    phone: Optional[str] = None
    address: Optional[str] = None
    city: Optional[str] = None
    state: Optional[str] = None
    country: Optional[str] = None
    postal_code: Optional[str] = None
    # Company-only
    website: Optional[str] = None
    industry: Optional[str] = None
    company_size: Optional[str] = None
    # Employee-only
    department: Optional[str] = None
    designation: Optional[str] = None
