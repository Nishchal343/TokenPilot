from sqlalchemy import Column, Integer, String, DateTime, Text
from sqlalchemy.sql import func

from app.core.database import Base


class SecurityLog(Base):
    __tablename__ = "security_logs"

    id = Column(Integer, primary_key=True, index=True)
    user_type = Column(String(20), nullable=False)  # 'company' or 'employee'
    user_id = Column(Integer, nullable=False, index=True)
    event_type = Column(String(50), nullable=False)  # login, logout, password_change, profile_update
    ip_address = Column(String(50), nullable=True)
    user_agent = Column(String(500), nullable=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)
