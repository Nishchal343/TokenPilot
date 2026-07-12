from sqlalchemy import (
    Column,
    Integer,
    String,
    Boolean,
    DateTime,
    Enum
)

from sqlalchemy.sql import func


from app.core.database import Base


from app.models.enums import OTPPurpose


class OTP(Base):
    __tablename__ = "otps"

    id = Column(Integer, primary_key=True)

    email = Column(
        String(255),
        nullable=False,
        index=True
    )

    otp_code = Column(
        String(6),
        nullable=False
    )

    purpose = Column(
        Enum(OTPPurpose),
        nullable=False
    )

    expires_at = Column(
        DateTime(timezone=True),
        nullable=False
    )

    is_used = Column(
        Boolean,
        default=False
    )

    created_at = Column(
        DateTime(timezone=True),
        server_default=func.now()
    )