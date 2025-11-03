from fastapi import FastAPI, Depends, HTTPException, UploadFile, File, Form, BackgroundTasks
from fastapi.staticfiles import StaticFiles
from fastapi.middleware.cors import CORSMiddleware
from sqlalchemy.orm import Session
import os
from datetime import datetime
from typing import List, Optional

from app.core.database import engine, get_db
from app.core.config import settings
from app.models import models
from app.api import upload, scheduling, analytics, auth
from app.tasks.celery_app import celery_app

# Create database tables
models.Base.metadata.create_all(bind=engine)

# Initialize FastAPI app
app = FastAPI(
    title="Social Media Automation Platform",
    description="Automated posting and analytics for social media platforms",
    version="1.0.0"
)

# CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # Configure appropriately for production
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Mount static files
os.makedirs("app/static", exist_ok=True)
os.makedirs(settings.UPLOAD_DIR, exist_ok=True)
app.mount("/static", StaticFiles(directory="app/static"), name="static")
app.mount("/uploads", StaticFiles(directory=settings.UPLOAD_DIR), name="uploads")

# Include routers
app.include_router(auth.router, prefix="/api/auth", tags=["authentication"])
app.include_router(upload.router, prefix="/api/upload", tags=["file-upload"])
app.include_router(scheduling.router, prefix="/api/schedule", tags=["scheduling"])
app.include_router(analytics.router, prefix="/api/analytics", tags=["analytics"])


@app.get("/")
async def root():
    from fastapi.responses import RedirectResponse
    return RedirectResponse(url="/static/index.html")

@app.get("/api/status")
async def api_status():
    return {
        "message": "Social Media Automation Platform",
        "version": "1.0.0",
        "docs": "/docs",
        "status": "running"
    }


@app.get("/health")
async def health_check():
    return {"status": "healthy", "timestamp": datetime.now()}


@app.get("/api/platforms")
async def get_supported_platforms():
    """Get list of supported social media platforms"""
    return {
        "platforms": [
            {"id": "instagram", "name": "Instagram", "supported_formats": ["jpg", "jpeg", "png", "mp4"]},
            {"id": "facebook", "name": "Facebook", "supported_formats": ["jpg", "jpeg", "png", "mp4", "gif"]},
            {"id": "twitter", "name": "Twitter/X", "supported_formats": ["jpg", "jpeg", "png", "gif", "mp4"]},
            {"id": "youtube", "name": "YouTube", "supported_formats": ["mp4", "avi", "mov"]},
            {"id": "tiktok", "name": "TikTok", "supported_formats": ["mp4", "mov"]}
        ]
    }


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)