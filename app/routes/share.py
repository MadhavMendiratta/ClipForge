"""Shareable video link endpoints."""

from datetime import UTC, datetime, timedelta
from typing import Optional

from fastapi import APIRouter, HTTPException, Query
from fastapi.responses import StreamingResponse
from pydantic import BaseModel, Field

from app.models.database import (
    create_share_token,
    get_share_token,
    increment_share_views,
    validate_share_token,
)
from app.utils.files import get_metadata, get_video_file

router = APIRouter()


class ShareCreateRequest(BaseModel):
    """Request body for creating a share link."""

    expires_in_hours: Optional[float] = Field(
        default=None,
        gt=0,
        description="Number of hours until the link expires (null = never)",
    )
    max_views: Optional[int] = Field(
        default=None,
        gt=0,
        description="Maximum number of views allowed (null = unlimited)",
    )


class ShareResponse(BaseModel):
    """Response model for a share link."""

    id: str
    video_id: str
    token: str
    share_url: str
    expires_at: Optional[str]
    max_views: Optional[int]
    current_views: int
    created_at: str


# ── Share creation (under /api) ──────────────────────────────────────────────

api_router = APIRouter()


@api_router.post("/video/{video_id}/share", response_model=ShareResponse, status_code=201)
async def create_share_link(video_id: str, body: ShareCreateRequest = ShareCreateRequest()) -> dict:
    """
    Generate a shareable link for a video.

    Args:
        video_id: UUID of the video to share.
        body: Share link options (expiry, max views).

    Returns:
        Share token details including the public URL.
    """
    # Verify the video exists
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

    token_data["share_url"] = f"/public/video/{token_data['token']}"
    return token_data


# ── Public video streaming (under /public) ───────────────────────────────────

public_router = APIRouter()


def _video_stream_generator(video_path: str, chunk_size: int = 1024 * 1024):
    """Stream a video file in chunks."""
    with open(video_path, "rb") as f:
        while chunk := f.read(chunk_size):
            yield chunk


@public_router.get("/video/{token}")
async def stream_shared_video(
    token: str,
    type: str = Query("processed", description="original or processed"),
):
    """
    Stream a video via a share token.

    Validates the token, checks expiry and view limits, then streams the video
    reusing the same streaming logic as the main video endpoint.

    Args:
        token: The share token string.
        type: Whether to stream original or processed video.

    Returns:
        StreamingResponse containing the video.
    """
    token_data = get_share_token(token)
    if token_data is None:
        raise HTTPException(status_code=404, detail="Invalid or unknown share link")

    # Validate token
    is_valid, reason = validate_share_token(token_data)
    if not is_valid:
        raise HTTPException(status_code=403, detail=reason)

    # Get the video file
    video_id = token_data["video_id"]
    try:
        video_path, content_type = get_video_file(
            video_id, processed=(type == "processed")
        )
    except HTTPException:
        raise HTTPException(status_code=404, detail="Video file not found")

    # Increment view count
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
