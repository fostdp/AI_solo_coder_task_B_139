from fastapi import APIRouter, HTTPException
import json
from pathlib import Path
from .schemas import DynastyComparisonRequest, DynastyComparisonResponse
from .service import dynasty_comparison_service

router = APIRouter(prefix="/api/dynasty", tags=["Craft Comparator"])


@router.post("/compare", response_model=DynastyComparisonResponse)
async def compare_dynasties(request: DynastyComparisonRequest):
    try:
        result = dynasty_comparison_service.compare_dynasties(
            request.dynasty_codes,
            request.wind_speed,
            request.soil_moisture,
            request.duration_hours,
            request.climate_scenario
        )
        return result
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/list")
async def list_dynasties():
    try:
        config_path = Path(__file__).parent.parent.parent.parent / "config" / "dynasty_craft_params.json"
        with open(config_path, "r", encoding="utf-8") as f:
            config = json.load(f)
        dynasties = []
        for code, dyn in config.get("dynasties", {}).items():
            dynasties.append({
                "code": code,
                "name": dyn.get("name", code),
                "period": dyn.get("period", ""),
                "craft_name": dyn.get("craft_name", ""),
                "description": dyn.get("description", ""),
                "compaction_ratio": dyn.get("parameters", {}).get("compaction_ratio", 0),
                "hardness_multiplier": dyn.get("erosion_properties", {}).get("hardness_multiplier", 1.0),
                "erosion_rate_modifier": dyn.get("erosion_properties", {}).get("erosion_rate_modifier", 1.0),
                "historical_examples": dyn.get("historical_examples", [])
            })
        return {"dynasties": dynasties, "climate_scenarios": config.get("simulation", {}).get("climate_scenarios", {})}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
