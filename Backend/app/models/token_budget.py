from sqlalchemy import Column, DateTime, Float, ForeignKey, Integer, UniqueConstraint
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func

from app.core.database import Base


class TokenBudget(Base):
    __tablename__ = "token_budgets"
    __table_args__ = (UniqueConstraint("company_id", "employee_id", name="uq_token_budget_company_employee"),)

    id = Column(Integer, primary_key=True, index=True)
    company_id = Column(Integer, ForeignKey("companies.id"), nullable=False, index=True)
    employee_id = Column(Integer, ForeignKey("employees.id"), nullable=False, index=True)
    monthly_limit = Column(Integer, nullable=False, default=0)
    used_tokens = Column(Integer, nullable=False, default=0)
    remaining_tokens = Column(Integer, nullable=False, default=0)
    total_requests = Column(Integer, nullable=False, default=0)
    gpt_requests = Column(Integer, nullable=False, default=0)
    gemini_requests = Column(Integer, nullable=False, default=0)
    claude_requests = Column(Integer, nullable=False, default=0)
    other_requests = Column(Integer, nullable=False, default=0)
    estimated_cost = Column(Float, nullable=False, default=0)
    last_used_at = Column(DateTime(timezone=True), nullable=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    updated_at = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now(), nullable=False)

    company = relationship("Company")
    employee = relationship("Employee")
