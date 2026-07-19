from datetime import datetime, timezone

from app.models.employee import Employee
from app.models.token_budget import TokenBudget


def get_or_create_budget(db, employee: Employee) -> TokenBudget:
    budget = db.query(TokenBudget).filter(TokenBudget.employee_id == employee.id).first()
    if not budget:
        budget = TokenBudget(company_id=employee.company_id, employee_id=employee.id)
        db.add(budget)
        db.flush()
    return budget


def record_usage(db, employee: Employee, tokens: int, model: str, estimated_cost: float = 0) -> TokenBudget:
    """Record a completed AI request; provider integrations can call this later."""
    if tokens < 0:
        raise ValueError("tokens must be non-negative")
    budget = get_or_create_budget(db, employee)
    budget.used_tokens += tokens
    budget.remaining_tokens = max(budget.monthly_limit - budget.used_tokens, 0)
    budget.total_requests += 1
    budget.estimated_cost += estimated_cost
    budget.last_used_at = datetime.now(timezone.utc)
    normalized = (model or "other").lower()
    if "gpt" in normalized or "openai" in normalized:
        budget.gpt_requests += 1
    elif "gemini" in normalized:
        budget.gemini_requests += 1
    elif "claude" in normalized or "anthropic" in normalized:
        budget.claude_requests += 1
    else:
        budget.other_requests += 1
    return budget


def reset_budget(budget: TokenBudget) -> None:
    budget.used_tokens = 0
    budget.remaining_tokens = budget.monthly_limit
    budget.total_requests = 0
    budget.gpt_requests = 0
    budget.gemini_requests = 0
    budget.claude_requests = 0
    budget.other_requests = 0
    budget.estimated_cost = 0
    budget.last_used_at = None
