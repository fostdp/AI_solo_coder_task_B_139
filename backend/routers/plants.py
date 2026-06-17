from fastapi import APIRouter, HTTPException
from typing import List, Dict, Any
from ..models.new_schemas import (
    PlantRootSimulationRequest,
    PlantRootSimulationResponse
)
from ..services.plant_root_simulation import plant_root_service

router = APIRouter(prefix="/api/plants", tags=["Plant Root Protection"])


@router.post("/simulate", response_model=PlantRootSimulationResponse)
async def simulate_plant_protection(request: PlantRootSimulationRequest):
    try:
        result = plant_root_service.simulate_plant_protection(
            request.plant_codes,
            request.coverage_pct,
            request.wall_height_m,
            request.wind_speed,
            request.soil_moisture,
            request.season
        )
        return result
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/species")
async def list_plant_species():
    try:
        plants = plant_root_service.get_available_plants()
        return {"plants": plants}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
