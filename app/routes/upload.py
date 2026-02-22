import logging
import os
import uuid
from typing import Any, Dict, Optional

from fastapi import APIRouter, BackgroundTasks, File, Form, HTTPException, UploadFile

from app.core.settings import settings
from app.models.database import get_preset
from app.utils.files import get_file_extension, get_video_path, save_upload_metadata
from app.utils.processing import process_video, video_processor

logger = logging.getLogger(__name__)

router = APIRouter()


@router.post("/upload")
async def upload_video(
    background_tasks: BackgroundTasks,
    video: UploadFile = File(...),
    edit_text: Optional[str] = Form(None),
    remove_silence: bool = Form(False),
    auto_crop_face: bool = Form(False),
    preset_id: Optional[str] = Form(None),
) -> Dict[str, Any]:
    """
    Upload a video file for processing.

    Args:
        background_tasks: FastAPI background tasks.
        video: The video file to be uploaded.
        edit_text: Optional natural language editing instructions (sent to LLM).
        remove_silence: Whether to detect and remove silent segments.
        auto_crop_face: Whether to auto-crop to 9:16 centered on face.
        preset_id: Optional preset UUID whose config is merged with request options.

    Returns:
        Dict containing the status, video ID, and applied processing options.
    """
    try:
        # Validate file extension
        extension = get_file_extension(video.filename)
        if extension not in settings.allowed_extensions:
            raise HTTPException(
                status_code=400,
                detail=f"File extension not allowed. Must be one of: {', '.join(settings.allowed_extensions)}",
            )

        # ── Load and merge preset ────────────────────────────────────────
        if preset_id:
            preset = get_preset(preset_id)
            if preset is None:
                raise HTTPException(status_code=404, detail="Preset not found")
            config = preset["config_json"]
            # Preset values are defaults; explicit request params override
            if edit_text is None:
                edit_text = config.get("edit_text")
            if not remove_silence:
                remove_silence = config.get("remove_silence", False)
            if not auto_crop_face:
                auto_crop_face = config.get("auto_crop_face", False)

        # ── Parse NL edit instructions via LLM ───────────────────────────
        edit_operations: Optional[list[dict[str, Any]]] = None
        if edit_text:
            from app.utils.llm import parse_edit_instructions

            try:
                result = await parse_edit_instructions(edit_text)
                edit_operations = result["operations"]
            except Exception as e:
                raise HTTPException(
                    status_code=422,
                    detail=f"Failed to parse edit instructions: {str(e)}",
                )

        # ── Save video file ──────────────────────────────────────────────
        os.makedirs(settings.upload_dir, exist_ok=True)
        video_id = str(uuid.uuid4())
        video_path = get_video_path(video_id, extension)

        contents = await video.read()
        with open(video_path, "wb") as f:
            f.write(contents)

        # ── Build processing options ─────────────────────────────────────
        processing_options: Dict[str, Any] = {}
        if edit_operations:
            processing_options["edit_operations"] = edit_operations
        if remove_silence:
            processing_options["remove_silence"] = True
        if auto_crop_face:
            processing_options["auto_crop_face"] = True

        # ── Save metadata ────────────────────────────────────────────────
        save_upload_metadata(
            video_id=video_id,
            original_filename=video.filename,
            file_size=len(contents),
            extension=extension,
            processing_options=processing_options,
        )

        # ── Start background processing ──────────────────────────────────
        background_tasks.add_task(process_video, video_id, video_processor)

        return {
            "status": "success",
            "message": "Video uploaded successfully and processing started",
            "video_id": video_id,
            "original_filename": video.filename,
            "extension": extension,
            "processing_options": processing_options,
        }

    except HTTPException:
        raise
    except Exception as e:
        if "video_path" in locals() and video_path.exists():
            video_path.unlink()

        raise HTTPException(
            status_code=500,
            detail=f"An error occurred while uploading the video: {str(e)}",
        )
