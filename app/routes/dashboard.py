import json
import logging
from pathlib import Path

from fastapi import APIRouter, Request
from fastapi.responses import HTMLResponse
from fastapi.templating import Jinja2Templates

from app.core.settings import settings

logger = logging.getLogger(__name__)

router = APIRouter()
templates = Jinja2Templates(directory="app/templates")


@router.get("/", response_class=HTMLResponse)
async def dashboard(request: Request):
    """Redirect root to upload page."""
    return templates.TemplateResponse(
        "upload.html", {"request": request, "active_page": "upload"}
    )


@router.get("/upload", response_class=HTMLResponse)
async def upload_page(request: Request):
    """Render the upload page."""
    return templates.TemplateResponse(
        "upload.html", {"request": request, "active_page": "upload"}
    )


@router.get("/video/{video_id}", response_class=HTMLResponse)
async def video_page(request: Request, video_id: str):
    """Render the video processing / result page."""
    return templates.TemplateResponse(
        "video.html", {"request": request, "video_id": video_id, "active_page": ""}
    )


@router.get("/videos", response_class=HTMLResponse)
async def videos_page(request: Request):
    """Render the my videos page."""
    return templates.TemplateResponse(
        "videos.html", {"request": request, "active_page": "videos"}
    )


@router.get("/health", response_class=HTMLResponse)
async def health_page(request: Request):
    """Render the system health page."""
    return templates.TemplateResponse(
        "health.html", {"request": request, "active_page": "health"}
    )


@router.get("/presets", response_class=HTMLResponse)
async def presets_page(request: Request):
    """Render the presets management page."""
    return templates.TemplateResponse(
        "presets.html", {"request": request, "active_page": "presets"}
    )
