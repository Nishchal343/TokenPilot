from sqlalchemy import (
    Column,
    Integer,
    String,
    Boolean,
    DateTime,
    ForeignKey,
    Enum,
)

from sqlalchemy.orm import relationship
from sqlalchemy.sql import func


from app.core.database import Base


from app.models.enums import EmployeeRole


class Employee(Base):
    __tablename__ = "employees"

    id = Column(Integer, primary_key=True, index=True)

    name = Column(String(255), nullable=False)

    email = Column(String(255), unique=True, nullable=False, index=True)

    password_hash = Column(String(255), nullable=False)

    is_verified = Column(Boolean, default=False)

    role = Column(
        Enum(EmployeeRole),
        nullable=True
    )

    company_id = Column(
        Integer,
        ForeignKey("companies.id"),
        nullable=True
    )

    invited_by_id = Column(
        Integer,
        ForeignKey("employees.id"),
        nullable=True
    )

    created_at = Column(
        DateTime(timezone=True),
        server_default=func.now()
    )

    company = relationship(
        "Company",
        back_populates="employees"
    )

    invited_by = relationship(
        "Employee",
        remote_side=[id]
    )