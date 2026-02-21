from typing import Any, Optional

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field, field_validator

from app.models.database import create_preset, get_preset, list_presets

router = APIRouter()


class PresetConfig(BaseModel):
    edit_text: Optional[str] = None
    remove_silence: Optional[bool] = None
    auto_crop_face: Optional[bool] = None

    @field_validator("edit_text")
    @classmethod
    def validate_edit_text(cls, v):
        if v is not None and not isinstance(v, str):
            raise ValueError("edit_text must be a string")
        return v


class PresetCreateRequest(BaseModel):
    name: str = Field(..., min_length=1, max_length=100)
    description: str = Field(default="", max_length=500)
    config_json: PresetConfig


class PresetResponse(BaseModel):
    id: str
    name: str
    description: str
    config_json: dict[str, Any]
    created_at: str


@router.get("/presets", response_model=list[PresetResponse])
async def get_presets():
    return list_presets()


@router.post("/presets", response_model=PresetResponse, status_code=201)
async def create_new_preset(body: PresetCreateRequest):
    preset = create_preset(
        name=body.name,
        config_json=body.config_json.model_dump(exclude_none=True),
        description=body.description,
    )
    return preset


@router.get("/presets/{preset_id}", response_model=PresetResponse)
async def get_preset_by_id(preset_id: str):
    preset = get_preset(preset_id)
    if preset is None:
        raise HTTPException(status_code=404, detail="Preset not found")
    return preset