from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
import uvicorn
from datetime import datetime
import asyncio

from app.api.routes import pipelines, metrics, health
from app.core.config import settings
from app.core.database import engine, Base, SessionLocal
from app.services.github_service import GitHubService

app = FastAPI(
    title="CI/CD Pipeline Health Dashboard",
    version="1.0.0",
    docs_url="/docs",
    redoc_url="/redoc",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(health.router, prefix="/api", tags=["health"])
app.include_router(pipelines.router, prefix="/api/pipelines", tags=["pipelines"])
app.include_router(metrics.router, prefix="/api/metrics", tags=["metrics"])

async def background_sync_task():
    """Periodically syncs GitHub data and triggers notifications."""
    await asyncio.sleep(10) # Initial delay to allow DB to be fully ready
    while True:
        print(f"--- Running background sync: {datetime.utcnow().isoformat()} ---")
        db = SessionLocal()
        try:
            github_service = GitHubService()
            synced_pipelines = await github_service.sync_workflow_runs(db)

            if synced_pipelines:
                print(f"Sync complete. Found {len(synced_pipelines)} new/updated runs.")
            else:
                print("Sync complete. No new updates found.")
        except Exception as e:
            print(f"ERROR in background task: {e}")
            db.rollback()
        finally:
            db.close()
        
        await asyncio.sleep(settings.SYNC_INTERVAL_SECONDS)

@app.on_event("startup")
async def on_startup():
    Base.metadata.create_all(bind=engine)
    asyncio.create_task(background_sync_task())
    print("🚀 Application startup complete. Background sync task scheduled.")

@app.get("/")
async def root():
    return {"message": "CI/CD Dashboard API is running"}
