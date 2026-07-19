from sqlalchemy import Boolean, Column, DateTime, ForeignKey, Integer, String, Text
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func

from app.core.database import Base


class Notification(Base):
    __tablename__ = "notifications"

    id = Column(Integer, primary_key=True, index=True)
    employee_id = Column(Integer, ForeignKey("employees.id"), nullable=False, index=True)
    title = Column(String(255), nullable=False)
    message = Column(Text, nullable=False)
    type = Column(String(100), nullable=False, index=True)
    is_read = Column(Boolean, nullable=False, default=False)
    created_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)

    employee = relationship("Employee", back_populates="notifications")
