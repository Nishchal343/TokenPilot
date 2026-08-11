from fastapi import FastAPI
from fastapi.staticfiles import StaticFiles
import os

from app.core.logging import setup_logging
from app.routers.auth import router as auth_router
from app.routers.invitations import router as invitations_router
from app.routers.organization import router as organization_router
from app.routers.notifications import router as notifications_router
from app.routers.dashboard import router as dashboard_router
from app.routers.token_budgets import router as token_budgets_router
from app.routers.profile import router as profile_router
from app.routers.settings import router as settings_router
from app.routers.security import router as security_router
from app.routers.support import router as support_router
from app.routers.api_key_requests import router as api_key_requests_router
from app.routers.workspace import router as workspace_router

setup_logging()

app = FastAPI(
    title="TokenPilot Backend",
    version="1.0.0",
    description="TokenPilot provider-routed AI workspace API"
)

# Serve uploaded files (avatars, screenshots)
os.makedirs("uploads", exist_ok=True)
app.mount("/uploads", StaticFiles(directory="uploads"), name="uploads")

app.include_router(auth_router)
app.include_router(invitations_router)
app.include_router(organization_router)
app.include_router(notifications_router)
app.include_router(dashboard_router)
app.include_router(token_budgets_router)
app.include_router(profile_router)
app.include_router(settings_router)
app.include_router(security_router)
app.include_router(support_router)
app.include_router(api_key_requests_router)
app.include_router(workspace_router)


@app.get("/")
def root():
    return {"message": "Backend Running Successfully"}
