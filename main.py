from contextlib import asynccontextmanager
from pathlib import Path
import os

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from dotenv import load_dotenv

from app.core.settings import settings
from app.routes import upload, video, health

load_dotenv()

BASE_DIR = Path(__file__).resolve().parent


@asynccontextmanager
async def lifespan(app: FastAPI):
    # Ensure required directories exist on startup
    settings.upload_dir.mkdir(parents=True, exist_ok=True)
    settings.processed_dir.mkdir(parents=True, exist_ok=True)
    yield


app = FastAPI(
    title="Video Processing API",
    description="A FastAPI application for video processing",
    version="1.0.0",
    debug=os.getenv("DEBUG", "False").lower() == "true",
    lifespan=lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.mount(
    "/static",
    StaticFiles(directory=str(BASE_DIR / "static")),
    name="static",
)

# Register API routers under /api
app.include_router(upload.router, prefix="/api", tags=["upload"])
app.include_router(video.router, prefix="/api", tags=["video"])
app.include_router(health.router, prefix="/api", tags=["health"])


@app.get("/")
def root():
    return {"message": "Video Processing API is running"}


if __name__ == "__main__":
    import uvicorn

    uvicorn.run(
        "main:app",
        host=os.getenv("HOST", "0.0.0.0"),
        port=int(os.getenv("PORT", 8000)),
        reload=os.getenv("DEBUG", "False").lower() == "true",
    )