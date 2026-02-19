import json
from datetime import UTC, datetime
from pathlib import Path
from typing import Any, Dict, Tuple

from fastapi import HTTPException
from app.core.settings import settings


def get_file_extension(filename: str) -> str:
    return Path(filename).suffix.replace(".", "").lower()


def save_upload_metadata(
    video_id: str,
    original_filename: str,
    file_size: int,
    extension: str,
    processing_options: Dict[str, Any] | None = None,
) -> None:
    metadata = {
        "video_id": video_id,
        "original_filename": original_filename,
        "file_size": file_size,
        "extension": extension,
        "upload_timestamp": datetime.now(UTC).isoformat(),
        "status": "uploaded",
        "mime_type": None,
        "processed": False,
        "progress": 0,
        "processing_details": {
            "current_step": "",
            "total_steps": 0,
            "current_step_progress": 0,
        },
        "processing_completed": None,
        "processing_options": processing_options or {},
    }

    metadata_path = settings.upload_dir / f"{video_id}.json"
    metadata_path.parent.mkdir(parents=True, exist_ok=True)

    with open(metadata_path, "w") as f:
        json.dump(metadata, f, indent=4)


def get_video_path(video_id: str, extension: str, processed: bool = False) -> Path:
    base_dir = settings.processed_dir if processed else settings.upload_dir
    prefix = settings.processed_prefix if processed else ""
    filename = f"{prefix}{video_id}.{extension}"
    return base_dir / filename


def get_metadata(video_id: str) -> Dict[str, Any]:
    metadata_path = settings.upload_dir / f"{video_id}.json"

    if not metadata_path.exists():
        raise HTTPException(status_code=404, detail="Video not found")

    try:
        with open(metadata_path, "r") as f:
            return json.load(f)
    except json.JSONDecodeError:
        raise HTTPException(status_code=500, detail="Metadata file corrupted")


def get_video_file(video_id: str, processed: bool = False) -> Tuple[Path, str]:
    metadata = get_metadata(video_id)

    if processed and not metadata.get("processed"):
        raise HTTPException(status_code=404, detail="Processed video not available")

    video_path = get_video_path(video_id, metadata["extension"], processed)

    if not video_path.exists():
        raise HTTPException(
            status_code=404,
            detail="Processed video not found" if processed else "Video file not found",
        )

    content_type = {
        "mp4": "video/mp4",
        "avi": "video/x-msvideo",
        "mov": "video/quicktime",
        "mkv": "video/x-matroska",
    }.get(metadata["extension"], "application/octet-stream")

    return video_path, content_type