from sqlalchemy import Boolean, Column, DateTime, ForeignKey, Integer, String, Text
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func

from app.core.database import Base


class APIKeyRequest(Base):
    __tablename__ = "api_key_requests"

    id = Column(Integer, primary_key=True, index=True)
    company_id = Column(Integer, ForeignKey("companies.id"), nullable=False, index=True)
    team_leader_id = Column(Integer, ForeignKey("employees.id"), nullable=False, index=True)
    employee_id = Column(Integer, ForeignKey("employees.id"), nullable=False, index=True)
    requested_tier = Column(String(20), nullable=False)
    requested_provider = Column(String(50), nullable=False, default="OpenAI")
    requested_model = Column(String(120), nullable=False)
    requested_budget = Column(Integer, nullable=False)
    leader_modified_budget = Column(Integer, nullable=True)
    company_final_budget = Column(Integer, nullable=True)
    status = Column(String(40), nullable=False, index=True)
    reason = Column(Text, nullable=False)
    rejection_reason = Column(Text, nullable=True)
    api_key_id = Column(Integer, ForeignKey("api_keys.id"), nullable=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    updated_at = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now(), nullable=False)

    company = relationship("Company")
    team_leader = relationship("Employee", foreign_keys=[team_leader_id])
    employee = relationship("Employee", foreign_keys=[employee_id])
    api_key = relationship("APIKey", foreign_keys=[api_key_id], post_update=True)
    audit_logs = relationship("APIKeyAuditLog", back_populates="request", cascade="all, delete-orphan")


class APIKey(Base):
    __tablename__ = "api_keys"

    id = Column(Integer, primary_key=True, index=True)
    company_id = Column(Integer, ForeignKey("companies.id"), nullable=False, index=True)
    employee_id = Column(Integer, ForeignKey("employees.id"), nullable=False, index=True)
    request_id = Column(Integer, nullable=True, index=True)
    provider = Column(String(50), nullable=False)
    model = Column(String(120), nullable=False)
    encrypted_api_key = Column(Text, nullable=False)
    budget_limit = Column(Integer, nullable=False)
    remaining_budget = Column(Integer, nullable=False)
    is_active = Column(Boolean, nullable=False, default=True)
    created_by = Column(Integer, nullable=False)
    created_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)

    company = relationship("Company")
    employee = relationship("Employee")


class APIKeyAuditLog(Base):
    __tablename__ = "api_key_audit_logs"

    id = Column(Integer, primary_key=True, index=True)
    request_id = Column(Integer, ForeignKey("api_key_requests.id"), nullable=False, index=True)
    actor_type = Column(String(20), nullable=False)
    actor_id = Column(Integer, nullable=False)
    action = Column(String(50), nullable=False)
    old_budget = Column(Integer, nullable=True)
    new_budget = Column(Integer, nullable=True)
    reason = Column(Text, nullable=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)

    request = relationship("APIKeyRequest", back_populates="audit_logs")
