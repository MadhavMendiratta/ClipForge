import uuid
from typing import Any, Dict, Optional

from fastapi import APIRouter, File, Form, HTTPException, UploadFile

from app.core.settings import settings
from app.utils.files import get_file_extension, get_video_path, save_upload_metadata

router = APIRouter()


@router.post("/upload")
async def upload_video(
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
    if edit_text:
        processing_options["edit_text"] = edit_text
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

    return {
        "status": "success",
        "video_id": video_id,
        "filename": video.filename,
        "processing_options": processing_options,
    }