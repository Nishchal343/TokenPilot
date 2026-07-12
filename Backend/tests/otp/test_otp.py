from datetime import datetime, timedelta, timezone

from app.core.database import SessionLocal
from app.models.enums import OTPPurpose
from app.models.otp import OTP
from app.services.otp_service import otp_service


def test_generate_otp():
    otp = otp_service.generate_otp()

    assert len(otp) == 6
    assert otp.isdigit()


def test_create_otp():

    db = SessionLocal()

    email = "otp_test@example.com"

    otp = otp_service.create_otp(
        db=db,
        email=email,
        purpose=OTPPurpose.register,
    )

    stored = (
        db.query(OTP)
        .filter(OTP.email == email)
        .order_by(OTP.created_at.desc())
        .first()
    )

    assert stored is not None
    assert stored.otp_code == otp
    assert stored.is_used is False

    db.close()


def test_only_one_active_otp():

    db = SessionLocal()

    email = "multiple@example.com"

    otp_service.create_otp(
        db=db,
        email=email,
        purpose=OTPPurpose.register,
    )

    otp_service.create_otp(
        db=db,
        email=email,
        purpose=OTPPurpose.register,
    )

    active_otps = (
        db.query(OTP)
        .filter(
            OTP.email == email,
            OTP.purpose == OTPPurpose.register,
            OTP.is_used.is_(False),
        )
        .all()
    )

    assert len(active_otps) == 1

    db.close()


def test_verify_valid_otp():

    db = SessionLocal()

    email = "valid@example.com"

    otp = otp_service.create_otp(
        db=db,
        email=email,
        purpose=OTPPurpose.register,
    )

    verified = otp_service.verify_otp(
        db=db,
        email=email,
        otp_code=otp,
        purpose=OTPPurpose.register,
    )

    assert verified is not None
    assert verified.email == email

    db.close()


def test_verify_wrong_otp():

    db = SessionLocal()

    email = "wrongotp@example.com"

    otp_service.create_otp(
        db=db,
        email=email,
        purpose=OTPPurpose.register,
    )

    verified = otp_service.verify_otp(
        db=db,
        email=email,
        otp_code="000000",
        purpose=OTPPurpose.register,
    )

    assert verified is None

    db.close()


def test_verify_wrong_email():

    db = SessionLocal()

    otp = otp_service.create_otp(
        db=db,
        email="correct@example.com",
        purpose=OTPPurpose.register,
    )

    verified = otp_service.verify_otp(
        db=db,
        email="wrong@example.com",
        otp_code=otp,
        purpose=OTPPurpose.register,
    )

    assert verified is None

    db.close()


def test_verify_wrong_purpose():

    db = SessionLocal()

    email = "purpose@example.com"

    otp = otp_service.create_otp(
        db=db,
        email=email,
        purpose=OTPPurpose.register,
    )

    verified = otp_service.verify_otp(
        db=db,
        email=email,
        otp_code=otp,
        purpose=OTPPurpose.reset_password,
    )

    assert verified is None

    db.close()


def test_verify_expired_otp():

    db = SessionLocal()

    email = "expired@example.com"

    otp = otp_service.create_otp(
        db=db,
        email=email,
        purpose=OTPPurpose.register,
    )

    record = (
        db.query(OTP)
        .filter(OTP.email == email)
        .order_by(OTP.created_at.desc())
        .first()
    )

    record.expires_at = (
        datetime.now(timezone.utc)
        - timedelta(minutes=1)
    )

    db.commit()

    verified = otp_service.verify_otp(
        db=db,
        email=email,
        otp_code=otp,
        purpose=OTPPurpose.register,
    )

    assert verified is None

    db.close()


def test_verify_used_otp():

    db = SessionLocal()

    email = "used@example.com"

    otp = otp_service.create_otp(
        db=db,
        email=email,
        purpose=OTPPurpose.register,
    )

    record = (
        db.query(OTP)
        .filter(OTP.email == email)
        .order_by(OTP.created_at.desc())
        .first()
    )

    record.is_used = True

    db.commit()

    verified = otp_service.verify_otp(
        db=db,
        email=email,
        otp_code=otp,
        purpose=OTPPurpose.register,
    )

    assert verified is None

    db.close()


def test_mark_otp_used():

    db = SessionLocal()

    email = "mark@example.com"

    otp = otp_service.create_otp(
        db=db,
        email=email,
        purpose=OTPPurpose.register,
    )

    record = otp_service.verify_otp(
        db=db,
        email=email,
        otp_code=otp,
        purpose=OTPPurpose.register,
    )

    otp_service.mark_otp_used(
        db=db,
        otp=record,
    )

    updated = (
        db.query(OTP)
        .filter(OTP.email == email)
        .order_by(OTP.created_at.desc())
        .first()
    )

    assert updated.is_used is True

    db.close()