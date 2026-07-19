from sqlalchemy import Column, Integer, String, Boolean, DateTime, Text
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func

from app.core.database import Base


class Company(Base):
    __tablename__ = "companies"

    id = Column(Integer, primary_key=True, index=True)
    name = Column(String(255), nullable=False)
    email = Column(String(255), unique=True, nullable=False, index=True)
    password_hash = Column(String(255), nullable=False)
    is_verified = Column(Boolean, default=False)
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    last_login_at = Column(DateTime(timezone=True), nullable=True)

    # Profile fields
    phone = Column(String(50), nullable=True)
    address = Column(String(500), nullable=True)
    city = Column(String(100), nullable=True)
    state = Column(String(100), nullable=True)
    country = Column(String(100), nullable=True)
    postal_code = Column(String(20), nullable=True)
    avatar_url = Column(String(500), nullable=True)
    website = Column(String(255), nullable=True)
    industry = Column(String(100), nullable=True)
    company_size = Column(String(50), nullable=True)

    employees = relationship("Employee", back_populates="company")