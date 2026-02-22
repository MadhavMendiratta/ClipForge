import asyncio
import json
import logging
from pathlib import Path
from typing import Dict, List, Literal

from fastapi import APIRouter, HTTPException, Query
from fastapi.responses import StreamingResponse
from sse_starlette.sse import EventSourceResponse

from app.core.settings import settings
from app.utils.files import get_metadata, get_video_file

logger = logging.getLogger(__name__)
router = APIRouter()

def video_stream_generator(video_path: str, chunk_size: int = 1024 * 1024):
    """
    Generator function to stream video file in chunks.

    Args:
        video_path: Path to the video file
        chunk_size: Size of each chunk in bytes (default: 1MB)

    Yields:
        Chunks of the video file
    """
    with open(video_path, "rb") as video:
        while chunk := video.read(chunk_size):
            yield chunk


@router.get("/video/{video_id}")
async def get_video(
    video_id: str,
    type: Literal["original", "processed"] = Query(
        "original", description="Type of video to retrieve"
    ),
):
    """
    Stream a video by its ID.

    Args:
        video_id: The ID of the video to stream
        type: Whether to stream the original or processed video

    Returns:
        StreamingResponse containing the video
    """
    try:
        video_path, content_type = get_video_file(
            video_id, processed=(type == "processed")
        )

        filename_prefix = "processed_" if type == "processed" else ""

        return StreamingResponse(
            video_stream_generator(str(video_path)),
            media_type=content_type,
            headers={
                "Accept-Ranges": "bytes",
                "Content-Disposition": (
                    f"inline; filename={filename_prefix}{video_id}{video_path.suffix}"
                ),
            },
        )
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail=f"An error occurred while streaming the video: {str(e)}",
        )


@router.get("/video/{video_id}/metadata")
async def get_video_metadata(video_id: str) -> Dict:
    """
    Get metadata for a video.

    Args:
        video_id: The ID of the video

    Returns:
        Dict containing video metadata
    """
    try:
        return get_metadata(video_id)
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail=f"An error occurred while retrieving metadata: {str(e)}",
        )


async def status_event_generator(video_id: str):
    """
    Generate SSE events for video processing status.

    Args:
        video_id: The ID of the video to monitor
    """
    while True:
        try:
            metadata = get_metadata(video_id)
            status = metadata.get("status", "unknown")

            data = {
                "status": status,
                "processed": metadata.get("processed", False),
                "processing_completed": metadata.get("processing_completed"),
                "video_id": video_id,
                "progress": metadata.get("progress", 0),
                "processing_details": metadata.get(
                    "processing_details",
                    {"current_step": "", "total_steps": 0, "current_step_progress": 0},
                ),
            }

            yield {"event": "status", "data": json.dumps(data)}

            # If processing is complete, failed, or reached 100%, stop sending events
            if (
                status in ["completed", "error"]
                or metadata.get("progress", 0) >= 100
                or metadata.get("processed", False)
            ):
                logger.info(f"Closing SSE connection for video {video_id}")
                break

            await asyncio.sleep(1)

        except HTTPException as he:
            yield {"event": "error", "data": json.dumps({"error": str(he.detail)})}
            break
        except Exception as e:
            yield {"event": "error", "data": json.dumps({"error": str(e)})}
            break


@router.get("/video/{video_id}/status/stream")
async def stream_video_status(video_id: str):
    """
    Stream video processing status updates using Server-Sent Events.

    Args:
        video_id: The ID of the video to monitor

    Returns:
        EventSourceResponse for status updates
    """
    return EventSourceResponse(
        status_event_generator(video_id), media_type="text/event-stream"
    )


@router.get("/videos/list")
async def list_videos() -> List[Dict]:
    """
    List all videos with their metadata.

    Returns:
        List of video metadata dicts, newest first.
    """
    upload_dir = Path(settings.upload_dir)
    if not upload_dir.exists():
        return []

    videos = []
    for meta_file in sorted(upload_dir.glob("*.json"), key=lambda p: p.stat().st_mtime, reverse=True):
        try:
            with open(meta_file) as f:
                data = json.load(f)
            videos.append(data)
        except Exception:
            continue

    return videos
