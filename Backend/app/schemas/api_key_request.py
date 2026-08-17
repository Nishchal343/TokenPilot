from datetime import datetime
from typing import Literal

from pydantic import BaseModel, Field, SecretStr


Tier = Literal["LOW", "MEDIUM", "HIGH"]
Provider = Literal["OpenAI", "Gemini", "Claude", "Groq", "Azure OpenAI", "OpenRouter", "Other"]


class APIKeyRequestCreate(BaseModel):
    requested_tier: Tier
    requested_provider: Provider
    requested_model: str = Field(..., min_length=1, max_length=120)
    requested_budget: int = Field(..., gt=0, le=2_000_000_000)
    reason: str = Field(..., min_length=1, max_length=2000)


class APIKeyRequestAction(BaseModel):
    action: Literal["approve", "reject"]
    modified_budget: int | None = Field(default=None, gt=0, le=2_000_000_000)
    reason: str | None = Field(default=None, max_length=2000)


class CompanyAPIKeyAction(BaseModel):
    action: Literal["approve", "reject"]
    provider: Provider | None = None
    api_key: SecretStr | None = None
    final_budget: int | None = Field(default=None, gt=0, le=2_000_000_000)
    reason: str | None = Field(default=None, max_length=2000)


class APIKeyCreate(BaseModel):
    request_id: int
    provider: Provider
    api_key: SecretStr
    final_budget: int = Field(..., gt=0, le=2_000_000_000)


class APIKeyRequestResponse(BaseModel):
    id: int
    company_id: int
    team_leader_id: int
    employee_id: int
    employee_name: str | None = None
    team_leader_name: str | None = None
    requested_tier: str
    requested_provider: str
    requested_model: str
    requested_budget: int
    leader_modified_budget: int | None
    company_final_budget: int | None
    status: str
    reason: str
    rejection_reason: str | None
    api_key_id: int | None
    created_at: datetime
    updated_at: datetime


class APIKeyResponse(BaseModel):
    id: int
    company_id: int
    employee_id: int
    request_id: int | None
    provider: str
    model: str
    budget_limit: int
    remaining_budget: int
    is_active: bool
    created_by: int
    created_at: datetime

    model_config = {"from_attributes": True}
