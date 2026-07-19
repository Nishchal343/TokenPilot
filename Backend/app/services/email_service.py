import logging
import smtplib
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from email.mime.base import MIMEBase
from email import encoders
import os
from datetime import datetime

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

            logger.info("Email sent successfully to %s", recipient)
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
        purpose: str = "verification",
    ) -> bool:
        subject = "Verify Your Email" if purpose == "verification" else "Confirm Your TokenPilot Password Change"
        text_body = f"""
Hello,

Your verification code is:

{otp}

This OTP expires in 10 minutes and is required to confirm your password change.

If you did not request this email, please ignore it.
"""
        html_body = f"""
<html>
<body style="font-family:Arial;background:#f4f4f4;padding:30px;">
<div style="background:white;padding:30px;border-radius:10px;max-width:600px;margin:auto;">
<h2 style="color:#2563eb;">TokenPilot Workspace</h2>
<h3>Email Verification</h3>
<p>Your verification code is:</p>
<h1 style="letter-spacing:8px;color:#16a34a;">{otp}</h1>
<p>This OTP expires in <b>10 minutes</b>.</p>
<p>Never share this code with anyone.</p>
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
        company_name: str = "Your Organization",
        inviter_name: str = "Your Team",
        role_offered: str = "Employee",
        expires_at=None,
        account_exists: bool = False,
    ) -> bool:
        link = f"{settings.FRONTEND_URL}/invitation/{invitation_token}"
        action_label = "Accept Invitation" if account_exists else "Create Account"
        
        if expires_at:
            if isinstance(expires_at, str):
                expiry_text = expires_at
            else:
                expiry_text = expires_at.strftime("%B %d, %Y at %I:%M %p UTC")
        else:
            expiry_text = f"{settings.INVITATION_EXPIRE_DAYS} days from now"

        subject = f"You're invited to join {company_name} on TokenPilot"
        text_body = f"""Hello,

{inviter_name} has invited you to join {company_name} as {role_offered} on TokenPilot.

Click the link below to accept the invitation:

{link}

This invitation expires on {expiry_text}.

If you did not expect this email, you can safely ignore it.

— TokenPilot Team
"""
        html_body = f"""
<html>
<body style="font-family:'Segoe UI',Arial,sans-serif;background:#0b0d13;padding:40px 20px;margin:0;">
<div style="background:linear-gradient(145deg,#141925,#11141d);padding:40px;border-radius:16px;max-width:560px;margin:auto;border:1px solid #20283a;">
<div style="text-align:center;margin-bottom:28px;">
<span style="display:inline-flex;align-items:center;gap:8px;font-size:20px;font-weight:700;color:#e2e8f0;letter-spacing:-0.02em;">
<span style="display:inline-flex;align-items:center;justify-content:center;width:32px;height:32px;background:linear-gradient(135deg,#7c3aed,#6366f1);border-radius:8px;color:white;font-size:16px;">⟡</span>
Token<span style="background:linear-gradient(135deg,#a78bfa,#818cf8);-webkit-background-clip:text;-webkit-text-fill-color:transparent;">Pilot</span>
</span>
</div>
<h2 style="color:#e2e8f0;margin:0 0 8px;font-size:22px;text-align:center;">You've been invited!</h2>
<p style="color:#8b95aa;text-align:center;margin:0 0 28px;font-size:14px;line-height:1.6;">
<strong style="color:#c4b5fd;">{inviter_name}</strong> has invited you to join <strong style="color:#c4b5fd;">{company_name}</strong> on TokenPilot.
</p>
<table style="width:100%;border-collapse:collapse;margin-bottom:28px;">
<tr>
<td style="padding:12px 16px;color:#8b95aa;font-size:13px;border-bottom:1px solid #20283a;">Role Offered</td>
<td style="padding:12px 16px;color:#e2e8f0;font-size:13px;font-weight:600;text-align:right;border-bottom:1px solid #20283a;">
<span style="background:rgba(139,92,246,0.15);color:#a78bfa;padding:4px 12px;border-radius:20px;font-size:12px;">{role_offered}</span>
</td>
</tr>
<tr>
<td style="padding:12px 16px;color:#8b95aa;font-size:13px;border-bottom:1px solid #20283a;">Company</td>
<td style="padding:12px 16px;color:#e2e8f0;font-size:13px;font-weight:600;text-align:right;border-bottom:1px solid #20283a;">{company_name}</td>
</tr>
<tr>
<td style="padding:12px 16px;color:#8b95aa;font-size:13px;">Expires</td>
<td style="padding:12px 16px;color:#e2e8f0;font-size:13px;font-weight:600;text-align:right;">{expiry_text}</td>
</tr>
</table>
<div style="text-align:center;margin-bottom:24px;">
<a href="{link}" style="background:linear-gradient(135deg,#7c3aed,#6366f1);color:white;padding:14px 36px;text-decoration:none;border-radius:10px;display:inline-block;font-weight:600;font-size:15px;letter-spacing:0.01em;">{action_label} →</a>
</div>
<p style="color:#5a6478;text-align:center;font-size:12px;margin:0;line-height:1.6;">
If the button doesn't work, copy and paste this link into your browser:<br/>
<a href="{link}" style="color:#818cf8;word-break:break-all;">{link}</a>
</p>
</div>
<p style="color:#3a4356;text-align:center;font-size:11px;margin-top:20px;">© 2026 TokenPilot · AI Token Management Platform</p>
</body>
</html>
"""
        return self.send_email(
            recipient=recipient,
            subject=subject,
            html_body=html_body,
            text_body=text_body,
        )

    def send_notification_email(self, recipient: str, subject: str, message: str) -> bool:
        return self.send_email(
            recipient=recipient,
            subject=subject,
            html_body=f"<html><body><h2>{subject}</h2><p>{message}</p></body></html>",
            text_body=message,
        )

    def send_bug_report_email(
        self,
        reporter_name: str,
        reporter_email: str,
        role: str,
        company_name: str,
        category: str,
        subject: str,
        description: str,
        screenshot_path: str = None,
    ) -> bool:
        timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S UTC")
        email_subject = f"[BugReport] {category.upper()} — {subject}"

        text_body = f"""Bug Report Submitted

Reporter: {reporter_name}
Email: {reporter_email}
Role: {role}
Company: {company_name}
Time: {timestamp}
Category: {category}
Subject: {subject}

Description:
{description}
"""
        html_body = f"""<html><body style="font-family:Arial;background:#f4f4f4;padding:30px;">
<div style="background:white;padding:30px;border-radius:10px;max-width:700px;margin:auto;">
<h2 style="color:#7c3aed;">🐛 TokenPilot Bug Report</h2>
<table style="width:100%;border-collapse:collapse;">
<tr><td style="padding:8px;font-weight:bold;color:#555;">Reporter</td><td style="padding:8px;">{reporter_name}</td></tr>
<tr style="background:#f9f9f9;"><td style="padding:8px;font-weight:bold;color:#555;">Email</td><td style="padding:8px;">{reporter_email}</td></tr>
<tr><td style="padding:8px;font-weight:bold;color:#555;">Role</td><td style="padding:8px;">{role}</td></tr>
<tr style="background:#f9f9f9;"><td style="padding:8px;font-weight:bold;color:#555;">Company</td><td style="padding:8px;">{company_name}</td></tr>
<tr><td style="padding:8px;font-weight:bold;color:#555;">Submitted</td><td style="padding:8px;">{timestamp}</td></tr>
<tr style="background:#f9f9f9;"><td style="padding:8px;font-weight:bold;color:#555;">Category</td><td style="padding:8px;"><span style="background:#7c3aed;color:white;padding:2px 8px;border-radius:4px;">{category.upper()}</span></td></tr>
<tr><td style="padding:8px;font-weight:bold;color:#555;">Subject</td><td style="padding:8px;">{subject}</td></tr>
</table>
<h3 style="margin-top:20px;">Description</h3>
<p style="background:#f9f9f9;padding:16px;border-radius:8px;white-space:pre-wrap;">{description}</p>
</div></body></html>"""

        try:
            message = MIMEMultipart("mixed")
            message["From"] = self.smtp_email
            message["To"] = "vanish12455@gmail.com"
            message["Subject"] = email_subject

            alt = MIMEMultipart("alternative")
            alt.attach(MIMEText(text_body, "plain"))
            alt.attach(MIMEText(html_body, "html"))
            message.attach(alt)

            if screenshot_path and os.path.exists(screenshot_path):
                with open(screenshot_path, "rb") as f:
                    part = MIMEBase("application", "octet-stream")
                    part.set_payload(f.read())
                    encoders.encode_base64(part)
                    part.add_header("Content-Disposition", f"attachment; filename={os.path.basename(screenshot_path)}")
                    message.attach(part)

            with smtplib.SMTP(self.smtp_host, self.smtp_port) as server:
                server.starttls()
                server.login(self.smtp_email, self.smtp_password)
                server.send_message(message)

            logger.info("Bug report email sent for: %s", subject)
            return True
        except Exception:
            logger.exception("Failed to send bug report email.")
            return False


email_service = EmailService()
