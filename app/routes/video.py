import json
from pathlib import Path
from typing import Dict, List, Literal

from fastapi import APIRouter, HTTPException, Query
from fastapi.responses import StreamingResponse

from app.core.settings import settings
from app.utils.files import get_metadata, get_video_file

router = APIRouter()


def video_stream_generator(video_path: str, chunk_size: int = 1024 * 1024):
    with open(video_path, "rb") as video:
        while chunk := video.read(chunk_size):
            yield chunk


@router.get("/video/{video_id}")
async def get_video(
    video_id: str,
    type: Literal["original", "processed"] = Query("original"),
):
    video_path, content_type = get_video_file(
        video_id, processed=(type == "processed")
    )

    filename_prefix = "processed_" if type == "processed" else ""

    return StreamingResponse(
        video_stream_generator(str(video_path)),
        media_type=content_type,
        headers={
            "Accept-Ranges": "bytes",
            "Content-Disposition": f"inline; filename={filename_prefix}{video_id}{video_path.suffix}",
        },
    )


@router.get("/video/{video_id}/metadata")
async def get_video_metadata(video_id: str) -> Dict:
    return get_metadata(video_id)


@router.get("/videos/list")
async def list_videos() -> List[Dict]:
    upload_dir = Path(settings.upload_dir)

    if not upload_dir.exists():
        return []

    videos = []
    for meta_file in sorted(
        upload_dir.glob("*.json"),
        key=lambda p: p.stat().st_mtime,
        reverse=True,
    ):
        try:
            with open(meta_file) as f:
                videos.append(json.load(f))
        except Exception:
            continue

    return videos