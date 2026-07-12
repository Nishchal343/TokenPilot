from sqlalchemy import (
    Column,
    Integer,
    String,
    DateTime,
    Enum
)

from sqlalchemy.sql import func


from app.core.database import Base

from app.models.enums import (
    InvitationStatus,
    InvitedByType,
    OfferedRole,
)



class Invitation(Base):
    __tablename__ = "invitations"

    id = Column(Integer, primary_key=True)

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

    created_at = Column(
        DateTime(timezone=True),
        server_default=func.now()
    )