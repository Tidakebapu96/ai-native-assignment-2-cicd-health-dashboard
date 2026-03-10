from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from sqlalchemy import text
from datetime import datetime, timezone
import time
import os

from app.core.database import get_db
from app.schemas.pipeline import HealthResponse
from app.services.github_service import GitHubService
from app.services.email_service import EmailService
from app.core.config import settings

router = APIRouter()

# Track application start time
START_TIME = time.time()

@router.get("/health", response_model=HealthResponse)
async def health_check(db: Session = Depends(get_db)):
    """Health check endpoint"""
    try:
        # Check database connection
        db.execute(text("SELECT 1"))
        db_status = "healthy"
    except Exception as e:
        db_status = f"unhealthy: {str(e)}"
    
    # Check GitHub API connection
    github_status = "not_configured"
    if settings.GITHUB_TOKEN:
        try:
            github_service = GitHubService()
            # Lightweight check: just verify the token by hitting /user
            async with __import__('httpx').AsyncClient() as client:
                resp = await client.get(
                    "https://api.github.com/user",
                    headers=github_service.headers,
                    timeout=5.0
                )
                github_status = "healthy" if resp.status_code == 200 else f"unhealthy: HTTP {resp.status_code}"
        except Exception as e:
            github_status = f"unhealthy: {str(e)}"
    
    # Calculate uptime
    uptime = time.time() - START_TIME
    
    return HealthResponse(
        status="healthy" if db_status == "healthy" else "unhealthy",
        timestamp=datetime.now(timezone.utc),
        version=settings.APP_VERSION,
        uptime=uptime,
        database=db_status,
        github=github_status,
        slack="disabled",
        email="enabled" if EmailService().enabled else "disabled"
    )

@router.get("/ping")
async def ping():
    """Simple ping endpoint"""
    return {"message": "pong", "timestamp": datetime.now(timezone.utc)}
