from sqlalchemy import (
    Column,
    Integer,
    String,
    DateTime,
    Enum,
    ForeignKey,
)

from sqlalchemy.sql import func
from sqlalchemy.orm import synonym

from app.core.database import Base

from app.models.enums import (
    InvitationStatus,
    InvitedByType,
    OfferedRole,
)


class Invitation(Base):
    __tablename__ = "invitations"

    id = Column(Integer, primary_key=True)

    name = Column(String(255), nullable=True)

    email = Column(
        String(255),
        nullable=False,
        index=True
    )

    invited_by_type = Column(
        Enum(InvitedByType),
        nullable=False
    )

    invited_by_id = Column(
        Integer,
        nullable=False
    )

    # Canonical RBAC ownership fields.  The legacy invited_by_* fields above
    # remain for compatibility with existing records and consumers.
    invited_by_user_id = Column(Integer, ForeignKey("employees.id"), nullable=True, index=True)
    company_id = Column(Integer, ForeignKey("companies.id"), nullable=True, index=True)

    manager_id = Column(Integer, ForeignKey("employees.id"), nullable=True)

    status = Column(
        Enum(InvitationStatus),
        default=InvitationStatus.pending
    )

    role_offered = Column(
        Enum(OfferedRole),
        nullable=False
    )

    token = Column(
        String(255),
        unique=True,
        nullable=False
    )

    token_expires_at = Column(
        DateTime(timezone=True),
        nullable=False
    )

    # Canonical names exposed alongside the existing API/database names.
    role = synonym("role_offered")
    expires_at = synonym("token_expires_at")

    created_at = Column(
        DateTime(timezone=True),
        server_default=func.now()
    )

    accepted_at = Column(DateTime(timezone=True), nullable=True)
    rejected_at = Column(DateTime(timezone=True), nullable=True)
    cancelled_at = Column(DateTime(timezone=True), nullable=True)
