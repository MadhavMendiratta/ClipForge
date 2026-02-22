"""File handling utilities for the application."""

import json
from datetime import UTC, datetime
from pathlib import Path
from typing import Any, Dict

from fastapi import HTTPException

from app.core.settings import settings


def get_file_extension(filename: str) -> str:
    """
    Extract the file extension from the filename.

    Args:
        filename: Original filename

    Returns:
        File extension without the dot
    """
    return Path(filename).suffix[1:].lower()


def save_upload_metadata(
    video_id: str,
    original_filename: str,
    file_size: int,
    extension: str,
    processing_options: Dict[str, Any] | None = None,
) -> None:
    """
    Save metadata about the uploaded video to a JSON file.

    Args:
        video_id: UUID of the video
        original_filename: Original name of the uploaded file
        file_size: Size of the file in bytes
        extension: File extension of the video
        processing_options: Optional dict of processing options
    """
    metadata = {
        "video_id": video_id,
        "original_filename": original_filename,
        "file_size": file_size,
        "extension": extension,
        "upload_timestamp": datetime.now(UTC).isoformat(),
        "status": "uploaded",  # Can be: uploaded, processing, completed, error
        "mime_type": None,  # Will be determined from the file
        "processed": False,
        "progress": 0,  # Processing progress percentage
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
    """
    Get the full path for a video file.

    Args:
        video_id: UUID of the video
        extension: File extension
        processed: Whether to get the processed video path

    Returns:
        Path object for the video file
    """
    base_dir = settings.processed_dir if processed else settings.upload_dir
    prefix = settings.processed_prefix if processed else ""
    filename = f"{prefix}{video_id}.{extension}"
    return base_dir / filename


def get_metadata(video_id: str) -> Dict[str, Any]:
    """
    Retrieve metadata for a video.

    Args:
        video_id: UUID of the video

    Returns:
        Dict containing video metadata

    Raises:
        HTTPException: If metadata file is not found
    """
    metadata_path = settings.upload_dir / f"{video_id}.json"
    if not metadata_path.exists():
        raise HTTPException(status_code=404, detail="Video not found")

    with open(metadata_path, "r") as f:
        try:
            return json.load(f)
        except json.JSONDecodeError:
            raise HTTPException(status_code=500, detail="Metadata file is corrupted")


def update_metadata_processing_status(
    video_id: str, status: str, processed: bool = False
) -> None:
    """
    Update the processing status in the video metadata.

    Args:
        video_id: UUID of the video
        status: New status to set
        processed: Whether the video has been processed
    """
    metadata = get_metadata(video_id)
    metadata["status"] = status
    metadata["processed"] = processed
    metadata["processing_completed"] = (
        datetime.now(UTC).isoformat() if processed else None
    )

    metadata_path = settings.upload_dir / f"{video_id}.json"
    with open(metadata_path, "w") as f:
        json.dump(metadata, f, indent=4)


def get_video_file(video_id: str, processed: bool = False) -> tuple[Path, str]:
    """
    Get the video file path and content type.

    Args:
        video_id: UUID of the video
        processed: Whether to get the processed video

    Returns:
        Tuple of (file path, content type)

    Raises:
        HTTPException: If video is not found or not processed yet
    """
    metadata = get_metadata(video_id)

    if processed and not metadata.get("processed"):
        raise HTTPException(status_code=404, detail="Processed video not available yet")

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


def update_processing_progress(
    video_id: str,
    progress: float,
    current_step: str = "",
    total_steps: int = 0,
    current_step_progress: float = 0,
) -> None:
    """
    Update the processing progress in the metadata.

    Args:
        video_id: UUID of the video
        progress: Overall progress percentage (0-100)
        current_step: Name of the current processing step
        total_steps: Total number of processing steps
        current_step_progress: Progress of the current step (0-100)
    """
    metadata = get_metadata(video_id)
    metadata["progress"] = min(
        100, max(0, progress)
    )  # Ensure progress is between 0 and 100
    metadata["processing_details"] = {
        "current_step": current_step,
        "total_steps": total_steps,
        "current_step_progress": min(100, max(0, current_step_progress)),
    }

    metadata_path = settings.upload_dir / f"{video_id}.json"
    with open(metadata_path, "w") as f:
        json.dump(metadata, f, indent=4)
