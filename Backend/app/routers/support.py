import logging
import os
import uuid
from typing import Optional

from fastapi import APIRouter, Depends, File, Form, HTTPException, UploadFile
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.core.dependencies import get_current_token_payload
from app.models.bug_report import BugReport
from app.models.company import Company
from app.models.employee import Employee
from app.schemas.auth import MessageResponse
from app.services.email_service import email_service

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/support", tags=["Support"])

SCREENSHOT_DIR = "uploads/screenshots"
os.makedirs(SCREENSHOT_DIR, exist_ok=True)
VALID_CATEGORIES = {"ui", "backend", "security", "performance", "other"}


@router.post("/report-bug", response_model=MessageResponse)
async def report_bug(
    category: str = Form(...),
    subject: str = Form(...),
    description: str = Form(...),
    screenshot: Optional[UploadFile] = None,
    db: Session = Depends(get_db),
    payload: dict = Depends(get_current_token_payload),
):
    # Validation
    category = category.strip()
    subject = subject.strip()
    description = description.strip()

    if not category or not subject or not description:
        raise HTTPException(status_code=400, detail="Category, subject, and description are required.")

    if category not in VALID_CATEGORIES:
        raise HTTPException(status_code=400, detail="Invalid bug category.")

    user_type = payload.get("type")
    if user_type == "company":
        user = db.query(Company).filter(Company.id == payload["company_id"]).first()
        role = "Company Admin"
        company_name = user.name if user else "Unknown"
        reporter_name = user.name if user else "Unknown"
        reporter_email = user.email if user else "Unknown"
    else:
        user = db.query(Employee).filter(Employee.id == payload["employee_id"]).first()
        role = "Team Lead" if user and user.role and user.role.value == "manager" else "Employee"
        company = db.query(Company).filter(Company.id == user.company_id).first() if user else None
        company_name = company.name if company else "Unknown"
        reporter_name = user.name if user else "Unknown"
        reporter_email = user.email if user else "Unknown"

    screenshot_path = None
    if screenshot and screenshot.filename:
        # Validate file size and type
        contents = await screenshot.read()
        if len(contents) > 10 * 1024 * 1024:
            raise HTTPException(status_code=400, detail="Screenshot must be under 10 MB.")
        
        # Verify content type is image
        content_type = screenshot.content_type or ""
        if not content_type.startswith("image/"):
            raise HTTPException(status_code=400, detail="Screenshot must be an image file.")

        ext = screenshot.filename.rsplit(".", 1)[-1] if "." in screenshot.filename else "png"
        filename = f"{uuid.uuid4().hex}.{ext}"
        screenshot_path = os.path.join(SCREENSHOT_DIR, filename)
        with open(screenshot_path, "wb") as f:
            f.write(contents)

    # Save to DB
    report = BugReport(
        reporter_name=reporter_name,
        reporter_email=reporter_email,
        role=role,
        company_name=company_name,
        category=category,
        subject=subject,
        description=description,
        screenshot_path=screenshot_path,
    )
    db.add(report)
    db.commit()

    # Send email
    email_sent = email_service.send_bug_report_email(
        reporter_name=reporter_name,
        reporter_email=reporter_email,
        role=role,
        company_name=company_name,
        category=category,
        subject=subject,
        description=description,
        screenshot_path=screenshot_path,
    )

    if not email_sent:
        logger.error("Failed to send bug report email for %s", reporter_email)
        # We still saved to DB, but inform user
        raise HTTPException(status_code=500, detail="Bug report logged, but failed to send email notification.")

    logger.info("Bug report submitted successfully by %s: %s", reporter_email, subject)
    return {"message": "Bug report submitted successfully. Thank you for your feedback!"}
