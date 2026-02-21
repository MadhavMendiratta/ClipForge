from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from app.routes import upload, video, dashboard, health
from app.routes import presets as presets_router
from app.routes.share import api_router as share_api_router, public_router as share_public_router
from app.models.database import init_db
from dotenv import load_dotenv
import os
from pathlib import Path

# Load environment variables
load_dotenv()

BASE_DIR = Path(__file__).resolve().parent


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Application lifespan: initialise resources on startup."""
    init_db()
    yield


app = FastAPI(
    title="Video Processing API",
    description="A FastAPI application for video processing",
    version="1.0.0",
    debug=os.getenv("DEBUG", "False").lower() == "true",
    lifespan=lifespan,
)

# Mount static files directory
app.mount("/static", StaticFiles(directory=str(BASE_DIR / "static")), name="static")

# Include routers
app.include_router(upload.router, prefix="/api", tags=["upload"])
app.include_router(video.router, prefix="/api", tags=["video"])
app.include_router(presets_router.router, prefix="/api", tags=["presets"])
app.include_router(share_api_router, prefix="/api", tags=["share"])
app.include_router(share_public_router, prefix="/public", tags=["public"])
app.include_router(dashboard.router, tags=["dashboard"])
app.include_router(health.router, prefix="/api", tags=["health"])

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(
        "main:app",
        host=os.getenv("HOST", "0.0.0.0"),
        port=int(os.getenv("PORT", 8000)),
        reload=os.getenv("DEBUG", "False").lower() == "true"
    )