import shutil
import sqlite3
import subprocess
import time
from typing import Dict

from fastapi import APIRouter

from app.core.settings import settings

router = APIRouter()


@router.get("/health")
async def health_check() -> Dict[str, str]:
    """
    Health check endpoint for container orchestration.

    Returns:
        Dict with status information
    """
    return {"status": "healthy"}


@router.get("/health/detailed")
async def detailed_health_check() -> Dict:
    """Detailed health check with dependency status."""
    start = time.time()
    result: Dict = {}

    # FFmpeg
    try:
        proc = subprocess.run(
            ["ffmpeg", "-version"], capture_output=True, text=True, timeout=5
        )
        version_line = proc.stdout.split("\n")[0] if proc.stdout else "unknown"
        result["ffmpeg"] = {"available": True, "version": version_line}
    except Exception:
        result["ffmpeg"] = {"available": False, "version": None}

    # Disk
    try:
        usage = shutil.disk_usage(".")
        result["disk"] = {
            "total_gb": round(usage.total / (1024**3), 1),
            "free_gb": round(usage.free / (1024**3), 1),
            "used_percent": round((usage.used / usage.total) * 100, 1),
        }
    except Exception:
        result["disk"] = {"total_gb": 0, "free_gb": 0, "used_percent": 0}

    # Database
    try:
        conn = sqlite3.connect(settings.database_path)
        cur = conn.cursor()
        presets_count = cur.execute("SELECT COUNT(*) FROM presets").fetchone()[0]
        tokens_count = cur.execute("SELECT COUNT(*) FROM share_tokens").fetchone()[0]
        conn.close()
        result["database"] = {
            "connected": True,
            "presets_count": presets_count,
            "share_tokens_count": tokens_count,
        }
    except Exception as e:
        result["database"] = {"connected": False, "error": str(e)}

    result["response_time_ms"] = round((time.time() - start) * 1000, 1)
    return result
