import logging
import secrets
from datetime import datetime, timedelta, timezone

from sqlalchemy.orm import Session

from app.core.config import settings
from app.models.enums import OTPPurpose
from app.models.otp import OTP

logger = logging.getLogger(__name__)


class OTPService:
    """
    Service responsible for generating, storing,
    and verifying OTPs.
    """

    OTP_LENGTH = 6

    def generate_otp(self) -> str:
        """
        Generate a secure 6-digit OTP.
        """

        otp = str(
            secrets.randbelow(900000) + 100000
        )

        logger.info("OTP generated successfully.")

        return otp

    def create_otp(
        self,
        db: Session,
        email: str,
        purpose: OTPPurpose,
    ) -> str:
        """
        Generate and store a new OTP.

        Any previous active OTPs for the same email and purpose
        are invalidated before creating a new one.
        """

        # Invalidate previous active OTPs
        existing_otps = (
            db.query(OTP)
            .filter(
                OTP.email == email,
                OTP.purpose == purpose,
                OTP.is_used.is_(False),
            )
            .all()
        )

        for existing_otp in existing_otps:
            existing_otp.is_used = True

        db.commit()

        logger.info(
            "Previous active OTPs invalidated for %s",
            email,
        )

        # Generate new OTP
        otp = self.generate_otp()

        expires_at = (
            datetime.now(timezone.utc)
            + timedelta(
                minutes=settings.OTP_EXPIRE_MINUTES
            )
        )

        otp_entry = OTP(
            email=email,
            otp_code=otp,
            purpose=purpose,
            expires_at=expires_at,
            is_used=False,
        )

        db.add(otp_entry)
        db.commit()
        db.refresh(otp_entry)

        logger.info(
            "New OTP stored successfully for %s",
            email,
        )

        return otp

    def verify_otp(
        self,
        db: Session,
        email: str,
        otp_code: str,
        purpose: OTPPurpose,
    ) -> OTP | None:
        """
        Verify an OTP.

        Returns:
            OTP object if valid.
            None otherwise.
        """

        otp = (
            db.query(OTP)
            .filter(
                OTP.email == email,
                OTP.otp_code == otp_code,
                OTP.purpose == purpose,
            )
            .first()
        )

        if otp is None:
            logger.warning(
                "OTP not found for %s",
                email,
            )
            return None

        if otp.is_used:
            logger.warning(
                "OTP already used for %s",
                email,
            )
            return None

        current_time = datetime.now(timezone.utc)

        if otp.expires_at < current_time:
            logger.warning(
                "OTP expired for %s",
                email,
            )
            return None

        logger.info(
            "OTP verified successfully for %s",
            email,
        )

        return otp

    def mark_otp_used(
        self,
        db: Session,
        otp: OTP,
    ) -> None:
        """
        Mark an OTP as used.
        """

        otp.is_used = True

        db.commit()

        db.refresh(otp)

        logger.info(
            "OTP marked as used for %s",
            otp.email,
        )


otp_service = OTPService()