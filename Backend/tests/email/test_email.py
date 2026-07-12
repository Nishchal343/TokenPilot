from app.services.email_service import email_service


def test_send_otp():

    success = email_service.send_otp_email(
        "nishchalk127@gmail.com",
        "123456"
    )

    assert success is True