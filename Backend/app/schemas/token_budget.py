from datetime import datetime
from pydantic import BaseModel, Field


class TokenBudgetCreate(BaseModel):
    employee_id: int
    monthly_limit: int = Field(..., ge=0)


class TokenBudgetUpdate(BaseModel):
    monthly_limit: int = Field(..., ge=0)


class TokenBudgetResponse(BaseModel):
    id: int
    company_id: int
    employee_id: int
    monthly_limit: int
    used_tokens: int
    remaining_tokens: int
    total_requests: int
    gpt_requests: int
    gemini_requests: int
    claude_requests: int
    other_requests: int
    estimated_cost: float
    last_used_at: datetime | None
    created_at: datetime
    updated_at: datetime

    model_config = {"from_attributes": True}
