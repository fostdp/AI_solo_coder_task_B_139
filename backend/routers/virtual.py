from fastapi import APIRouter, HTTPException
from typing import Dict, Any
from ..models.new_schemas import (
    VirtualExperienceRequest,
    VirtualExperienceResponse
)
from ..services.virtual_experience import virtual_experience_service

router = APIRouter(prefix="/api/virtual", tags=["Virtual Craft Experience"])


@router.post("/evaluate", response_model=VirtualExperienceResponse)
async def evaluate_mix(request: VirtualExperienceRequest):
    try:
        mix_dict = {
            "soil_pct": request.mix.soil_pct,
            "clay_pct": request.mix.clay_pct,
            "sand_pct": request.mix.sand_pct,
            "lime_pct": request.mix.lime_pct,
            "rice_paste_pct": request.mix.rice_paste_pct,
            "straw_pct": request.mix.straw_pct,
            "water_pct": request.mix.water_pct
        }
        result = virtual_experience_service.evaluate_mix(
            mix_dict,
            request.tamping_preset,
            request.wall_height_m,
            request.wind_speed
        )
        return result
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/presets")
async def get_presets():
    try:
        result = virtual_experience_service.get_material_presets()
        dynasties = virtual_experience_service.get_dynasty_presets()
        result["dynasty_presets"] = dynasties
        return result
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
