"""Preset management endpoints."""

from typing import Any

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field

from app.models.database import create_preset, get_preset, list_presets

router = APIRouter()


class PresetCreateRequest(BaseModel):
    """Request body for creating a preset."""

    name: str = Field(..., min_length=1, max_length=100, description="Preset name")
    description: str = Field(default="", max_length=500, description="Preset description")
    config_json: dict[str, Any] = Field(
        ...,
        description=(
            "Preset configuration. Supported keys: "
            "edit_text (str), remove_silence (bool), auto_crop_face (bool)"
        ),
    )


class PresetResponse(BaseModel):
    """Response model for a preset."""

    id: str
    name: str
    description: str
    config_json: dict[str, Any]
    created_at: str


@router.get("/presets", response_model=list[PresetResponse])
async def get_presets() -> list[dict[str, Any]]:
    """
    List all saved presets.

    Returns:
        List of preset objects.
    """
    return list_presets()


@router.post("/presets", response_model=PresetResponse, status_code=201)
async def create_new_preset(body: PresetCreateRequest) -> dict[str, Any]:
    """
    Create a new processing preset.

    Args:
        body: Preset creation payload.

    Returns:
        The created preset.
    """
    # Validate config keys
    allowed_keys = {"edit_text", "remove_silence", "auto_crop_face"}
    unknown = set(body.config_json.keys()) - allowed_keys
    if unknown:
        raise HTTPException(
            status_code=400,
            detail=f"Unknown config keys: {', '.join(unknown)}. Allowed: {', '.join(allowed_keys)}",
        )

    preset = create_preset(
        name=body.name,
        config_json=body.config_json,
        description=body.description,
    )
    return preset


@router.get("/presets/{preset_id}", response_model=PresetResponse)
async def get_preset_by_id(preset_id: str) -> dict[str, Any]:
    """
    Get a single preset by ID.

    Args:
        preset_id: UUID of the preset.

    Returns:
        The preset object.
    """
    preset = get_preset(preset_id)
    if preset is None:
        raise HTTPException(status_code=404, detail="Preset not found")
    return preset
