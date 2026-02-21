import uuid
from typing import Any, Dict, Optional

from fastapi import APIRouter, BackgroundTasks, File, Form, HTTPException, UploadFile

from app.core.settings import settings
from app.utils.files import get_file_extension, get_video_path, save_upload_metadata
from app.utils.processing import process_video, video_processor

router = APIRouter()


@router.post("/upload")
async def upload_video(
    background_tasks: BackgroundTasks,
    video: UploadFile = File(...),
    edit_text: Optional[str] = Form(None),
    remove_silence: bool = Form(False),
    auto_crop_face: bool = Form(False),
) -> Dict[str, Any]:

    extension = get_file_extension(video.filename)

    if extension not in settings.allowed_extensions:
        raise HTTPException(
            status_code=400,
            detail=f"File extension not allowed. Allowed: {', '.join(settings.allowed_extensions)}",
        )

    video_id = str(uuid.uuid4())
    video_path = get_video_path(video_id, extension)

    contents = await video.read()
    video_path.parent.mkdir(parents=True, exist_ok=True)

    with open(video_path, "wb") as f:
        f.write(contents)

    processing_options: Dict[str, Any] = {}

    # ✅ LLM integration
    if edit_text:
        from app.utils.llm import parse_edit_instructions

        try:
            result = await parse_edit_instructions(edit_text)
            processing_options["edit_operations"] = result["operations"]
        except Exception as e:
            raise HTTPException(
                status_code=422,
                detail=f"Failed to parse edit instructions: {str(e)}",
            )

    if remove_silence:
        processing_options["remove_silence"] = True

    if auto_crop_face:
        processing_options["auto_crop_face"] = True

    save_upload_metadata(
        video_id=video_id,
        original_filename=video.filename,
        file_size=len(contents),
        extension=extension,
        processing_options=processing_options,
    )

    # ✅ Switch to real processor (IMPORTANT CHANGE)
    background_tasks.add_task(process_video, video_id, video_processor)

    return {
        "status": "success",
        "message": "Video uploaded successfully. Processing started.",
        "video_id": video_id,
        "processing_options": processing_options,
    }