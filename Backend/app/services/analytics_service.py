from collections import Counter
from app.models.employee import Employee
from app.models.enums import EmployeeRole, InvitationStatus
from app.models.invitation import Invitation
from app.models.token_budget import TokenBudget


def descendants(root: Employee):
    result, stack = [], list(root.subordinates)
    while stack:
        current = stack.pop()
        result.append(current)
        stack.extend(current.subordinates)
    return result


def token_stats(budgets):
    values = list(budgets)
    return {
        "total_monthly_token_budget": sum(item.monthly_limit for item in values),
        "total_tokens_used": sum(item.used_tokens for item in values),
        "total_tokens_remaining": sum(item.remaining_tokens for item in values),
        "estimated_ai_cost": sum(item.estimated_cost for item in values),
        "total_ai_requests": sum(item.total_requests for item in values),
        "most_used_ai_model": max(("GPT", sum(x.gpt_requests for x in values)), ("Gemini", sum(x.gemini_requests for x in values)), ("Claude", sum(x.claude_requests for x in values)), ("Other", sum(x.other_requests for x in values)), key=lambda item: item[1])[0] if values else None,
    }


def invitation_counts(query, emails=None, invited_by_id=None):
    if emails is not None:
        query = query.filter(Invitation.email.in_(emails))
    if invited_by_id is not None:
        query = query.filter(Invitation.invited_by_id == invited_by_id)
    rows = query.all()
    return {status.value + "_invitations": sum(item.status == status for item in rows) for status in InvitationStatus}
