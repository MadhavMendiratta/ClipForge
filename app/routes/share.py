from datetime import UTC, datetime, timedelta
from typing import Optional, Literal

from fastapi import APIRouter, HTTPException, Query, Body
from fastapi.responses import StreamingResponse
from pydantic import BaseModel, Field

from app.models.database import (
    create_share_token,
    get_share_token,
    increment_share_views,
    validate_share_token,
)
from app.utils.files import get_metadata, get_video_file

# Routers
api_router = APIRouter()
public_router = APIRouter()


class ShareCreateRequest(BaseModel):
    expires_in_hours: Optional[float] = Field(default=None, gt=0)
    max_views: Optional[int] = Field(default=None, gt=0)


class ShareResponse(BaseModel):
    id: str
    video_id: str
    token: str
    share_url: str
    expires_at: Optional[str]
    max_views: Optional[int]
    current_views: int
    created_at: str


@api_router.post("/video/{video_id}/share", response_model=ShareResponse, status_code=201)
async def create_share_link(
    video_id: str,
    body: ShareCreateRequest = Body(...)
) -> dict:

    # Check video exists
    try:
        get_metadata(video_id)
    except HTTPException:
        raise HTTPException(status_code=404, detail="Video not found")

    expires_at: Optional[str] = None
    if body.expires_in_hours is not None:
        expires_at = (
            datetime.now(UTC) + timedelta(hours=body.expires_in_hours)
        ).isoformat()

    token_data = create_share_token(
        video_id=video_id,
        expires_at=expires_at,
        max_views=body.max_views,
    )

    # Change base URL if needed (prod vs local)
    BASE_URL = "http://localhost:8000"

    token_data["share_url"] = f"{BASE_URL}/public/video/{token_data['token']}"

    return token_data


def _video_stream_generator(video_path: str, chunk_size: int = 1024 * 1024):
    with open(video_path, "rb") as f:
        while chunk := f.read(chunk_size):
            yield chunk


@public_router.get("/video/{token}")
async def stream_shared_video(
    token: str,
    type: Literal["original", "processed"] = Query("processed"),
):

    token_data = get_share_token(token)
    if token_data is None:
        raise HTTPException(status_code=404, detail="Invalid or unknown share link")

    # Validate token
    is_valid, reason = validate_share_token(token_data)
    if not is_valid:
        raise HTTPException(status_code=403, detail=reason)

    video_id = token_data["video_id"]

    try:
        video_path, content_type = get_video_file(
            video_id, processed=(type == "processed")
        )
    except HTTPException:
        raise HTTPException(status_code=404, detail="Video file not found")

    # Increment views
    increment_share_views(token)

    filename_prefix = "processed_" if type == "processed" else ""

    return StreamingResponse(
        _video_stream_generator(str(video_path)),
        media_type=content_type,
        headers={
            "Accept-Ranges": "bytes",
            "Content-Disposition": (
                f"inline; filename={filename_prefix}{video_id}{video_path.suffix}"
            ),
        },
    )
