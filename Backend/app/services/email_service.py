import logging
import smtplib
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText

from app.core.config import settings

logger = logging.getLogger(__name__)


class EmailService:
    def __init__(self):
        self.smtp_host = settings.SMTP_HOST
        self.smtp_port = settings.SMTP_PORT
        self.smtp_email = settings.SMTP_EMAIL
        self.smtp_password = settings.SMTP_PASSWORD

    def send_email(
        self,
        recipient: str,
        subject: str,
        html_body: str,
        text_body: str,
    ) -> bool:
        """
        Generic email sender.

        Sends both HTML and plain-text versions of an email.

        Args:
            recipient: Recipient email address.
            subject: Email subject.
            html_body: HTML version of the email.
            text_body: Plain-text fallback.

        Returns:
            True if email is sent successfully, otherwise False.
        """

        try:
            message = MIMEMultipart("alternative")

            message["From"] = self.smtp_email
            message["To"] = recipient
            message["Subject"] = subject

            message.attach(MIMEText(text_body, "plain"))
            message.attach(MIMEText(html_body, "html"))

            with smtplib.SMTP(
                self.smtp_host,
                self.smtp_port,
            ) as server:

                server.starttls()

                server.login(
                    self.smtp_email,
                    self.smtp_password,
                )

                server.send_message(message)

            logger.info(
                "Email sent successfully to %s",
                recipient,
            )

            return True

        except smtplib.SMTPAuthenticationError:
            logger.exception("SMTP authentication failed.")

        except smtplib.SMTPException:
            logger.exception("SMTP error occurred.")

        except Exception:
            logger.exception("Unexpected email error.")

        return False

    def send_otp_email(
        self,
        recipient: str,
        otp: str,
    ) -> bool:

        subject = "Verify Your Email"

        text_body = f"""
Hello,

Your verification code is:

{otp}

This OTP expires in 10 minutes.

If you did not request this email, please ignore it.
"""

        html_body = f"""
<html>
<body style="font-family:Arial;background:#f4f4f4;padding:30px;">

<div style="
background:white;
padding:30px;
border-radius:10px;
max-width:600px;
margin:auto;
">

<h2 style="color:#2563eb;">
SaaS Hiring Platform
</h2>

<h3>Email Verification</h3>

<p>Your verification code is:</p>

<h1 style="
letter-spacing:8px;
color:#16a34a;
">
{otp}
</h1>

<p>
This OTP expires in <b>10 minutes</b>.
</p>

<p>
Never share this code with anyone.
</p>

</div>

</body>
</html>
"""

        return self.send_email(
            recipient=recipient,
            subject=subject,
            html_body=html_body,
            text_body=text_body,
        )

    def send_invitation_email(
        self,
        recipient: str,
        invitation_token: str,
    ) -> bool:

        link = (
            f"{settings.FRONTEND_URL}"
            f"/invite/accept?token={invitation_token}"
        )

        subject = "Company Invitation"

        text_body = f"""
Hello,

You've been invited to join a company.

Click the link below:

{link}

This invitation expires in {settings.INVITATION_EXPIRE_DAYS} days.
"""

        html_body = f"""
<html>
<body style="font-family:Arial;background:#f4f4f4;padding:30px;">

<div style="
background:white;
padding:30px;
border-radius:10px;
max-width:600px;
margin:auto;
">

<h2 style="color:#2563eb;">
Company Invitation
</h2>

<p>
You have been invited to join a company.
</p>

<a
href="{link}"
style="
background:#2563eb;
color:white;
padding:12px 18px;
text-decoration:none;
border-radius:8px;
display:inline-block;
">
Accept Invitation
</a>

<p style="margin-top:20px;">
Invitation expires in
<b>{settings.INVITATION_EXPIRE_DAYS} days.</b>
</p>

</div>

</body>
</html>
"""

        return self.send_email(
            recipient=recipient,
            subject=subject,
            html_body=html_body,
            text_body=text_body,
        )


email_service = EmailService()