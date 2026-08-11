import logging
import os
import shutil
import uuid
from typing import Optional

from fastapi import APIRouter, Depends, File, HTTPException, UploadFile
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.core.dependencies import get_current_token_payload
from app.models.company import Company
from app.models.employee import Employee
from app.schemas.auth import MessageResponse
from app.schemas.profile import ProfileResponse, ProfileUpdateRequest

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/profile", tags=["Profile"])

UPLOAD_DIR = "uploads/avatars"
os.makedirs(UPLOAD_DIR, exist_ok=True)
ALLOWED_TYPES = {"image/jpeg", "image/png", "image/jpg"}
MAX_SIZE = 5 * 1024 * 1024  # 5 MB


def _get_user(db: Session, payload: dict):
    if payload.get("type") == "company":
        company = db.query(Company).filter(Company.id == payload["company_id"]).first()
        if not company:
            raise HTTPException(status_code=404, detail="Company not found")
        return "company", company
    else:
        employee = db.query(Employee).filter(Employee.id == payload["employee_id"]).first()
        if not employee:
            raise HTTPException(status_code=404, detail="Employee not found")
        return "employee", employee


@router.get("", response_model=ProfileResponse)
def get_profile(db: Session = Depends(get_db), payload: dict = Depends(get_current_token_payload)):
    user_type, user = _get_user(db, payload)
    result = {
        "name": user.name,
        "email": user.email,
        "role": "Company Admin" if user_type == "company" else (
            "Team Lead" if getattr(user, "role", None) and user.role.value == "manager" else "Employee"
        ),
        "phone": getattr(user, "phone", None),
        "address": getattr(user, "address", None),
        "city": getattr(user, "city", None),
        "state": getattr(user, "state", None),
        "country": getattr(user, "country", None),
        "postal_code": getattr(user, "postal_code", None),
        "avatar_url": getattr(user, "avatar_url", None),
    }
    if user_type == "company":
        result["company_name"] = user.name
        result["website"] = user.website
        result["industry"] = user.industry
        result["company_size"] = user.company_size
    else:
        company = db.query(Company).filter(Company.id == user.company_id).first()
        result["company_name"] = company.name if company else None
        result["department"] = user.department
        result["designation"] = user.designation
        result["reporting_manager"] = user.manager.name if user.manager else None
        result["manager_id"] = user.manager_id
    return result


@router.patch("", response_model=MessageResponse)
def update_profile(
    body: ProfileUpdateRequest,
    db: Session = Depends(get_db),
    payload: dict = Depends(get_current_token_payload),
):
    user_type, user = _get_user(db, payload)
    update_fields = body.model_dump(exclude_none=True)
    # Only allow company-specific fields for company, employee-specific for employee
    if user_type == "company":
        update_fields.pop("department", None)
        update_fields.pop("designation", None)
    else:
        update_fields.pop("website", None)
        update_fields.pop("industry", None)
        update_fields.pop("company_size", None)

    for field, value in update_fields.items():
        if hasattr(user, field):
            setattr(user, field, value)
    db.commit()
    logger.info("Profile updated for %s id=%s", user_type, user.id)
    return {"message": "Profile updated successfully."}


@router.post("/avatar", response_model=MessageResponse)
async def upload_avatar(
    file: UploadFile = File(...),
    db: Session = Depends(get_db),
    payload: dict = Depends(get_current_token_payload),
):
    if file.content_type not in ALLOWED_TYPES:
        raise HTTPException(status_code=400, detail="Only JPG and PNG images are allowed.")

    contents = await file.read()
    if len(contents) > MAX_SIZE:
        raise HTTPException(status_code=400, detail="File size must be under 5 MB.")

    ext = "jpg" if "jpeg" in file.content_type else "png"
    filename = f"{uuid.uuid4().hex}.{ext}"
    filepath = os.path.join(UPLOAD_DIR, filename)

    with open(filepath, "wb") as f:
        f.write(contents)

    user_type, user = _get_user(db, payload)
    # Remove old avatar file
    if user.avatar_url:
        old_path = user.avatar_url.lstrip("/")
        if os.path.exists(old_path):
            os.remove(old_path)

    user.avatar_url = f"/{filepath}"
    db.commit()
    logger.info("Avatar uploaded for %s id=%s -> %s", user_type, user.id, filepath)
    return {"message": "Avatar uploaded successfully."}


@router.delete("/avatar", response_model=MessageResponse)
def delete_avatar(
    db: Session = Depends(get_db),
    payload: dict = Depends(get_current_token_payload),
):
    user_type, user = _get_user(db, payload)
    if user.avatar_url:
        old_path = user.avatar_url.lstrip("/")
        if os.path.exists(old_path):
            try:
                os.remove(old_path)
            except Exception:
                logger.warning("Failed to remove avatar file %s", old_path)
        user.avatar_url = None
        db.commit()
        logger.info("Avatar removed for %s id=%s", user_type, user.id)
        return {"message": "Profile photo removed successfully."}
    
    return {"message": "No profile photo to remove."}
