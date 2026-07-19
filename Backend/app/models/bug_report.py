from sqlalchemy import Column, Integer, String, DateTime, Text
from sqlalchemy.sql import func

from app.core.database import Base


class BugReport(Base):
    __tablename__ = "bug_reports"

    id = Column(Integer, primary_key=True, index=True)
    reporter_name = Column(String(255), nullable=False)
    reporter_email = Column(String(255), nullable=False)
    role = Column(String(100), nullable=False)
    company_name = Column(String(255), nullable=True)
    category = Column(String(50), nullable=False)  # ui, backend, security, performance, other
    subject = Column(String(500), nullable=False)
    description = Column(Text, nullable=False)
    screenshot_path = Column(String(500), nullable=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)
