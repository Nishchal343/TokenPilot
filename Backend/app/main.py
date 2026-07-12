from fastapi import FastAPI

from app.core.logging import setup_logging

setup_logging()

app = FastAPI(
    title="SaaS Hiring Backend",
    version="1.0.0",
    description="Authentication and Hiring API"
)


@app.get("/")
def root():
    return {
        "message": "Backend Running Successfully"
    }