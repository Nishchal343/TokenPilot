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

    manager_id = Column(
        Integer,
        ForeignKey("employees.id"),
        nullable=True,
        index=True,
    )

    created_at = Column(
        DateTime(timezone=True),
        server_default=func.now()
    )
    last_login_at = Column(DateTime(timezone=True), nullable=True)

    # Profile fields
    phone = Column(String(50), nullable=True)
    address = Column(String(500), nullable=True)
    city = Column(String(100), nullable=True)
    state = Column(String(100), nullable=True)
    country = Column(String(100), nullable=True)
    postal_code = Column(String(20), nullable=True)
    avatar_url = Column(String(500), nullable=True)
    department = Column(String(100), nullable=True)
    designation = Column(String(100), nullable=True)

    company = relationship(
        "Company",
        back_populates="employees"
    )

    invited_by = relationship(
        "Employee",
        remote_side=[id],
        foreign_keys=[invited_by_id],
    )

    manager = relationship(
        "Employee",
        remote_side=[id],
        foreign_keys=[manager_id],
        back_populates="subordinates",
    )

    subordinates = relationship(
        "Employee",
        foreign_keys=[manager_id],
        back_populates="manager",
    )

    notifications = relationship(
        "Notification",
        back_populates="employee",
        cascade="all, delete-orphan",
    )
