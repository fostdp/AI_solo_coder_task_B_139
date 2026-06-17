from pydantic import BaseModel, Field
from typing import Optional, List, Dict, Any


class PlantRootSimulationRequest(BaseModel):
    plant_codes: List[str] = ["GRASS_DEEP", "SHRUB"]
    coverage_pct: float = 70.0
    wall_height_m: float = 2.5
    wind_speed: float = 8.0
    soil_moisture: float = 5.0
    season: Optional[str] = "summer"


class PlantProtectionEffect(BaseModel):
    plant_code: str
    name: str
    name_zh: Optional[str] = None
    root_depth_mm: Optional[float] = None
    erosion_reduction_pct: float
    wind_speed_reduction_pct: float
    cohesion_increase_kpa: float
    seasonal_factor: Optional[float] = None
    effective_coverage_ratio: Optional[float] = None


class PlantRootSimulationResponse(BaseModel):
    request: PlantRootSimulationRequest
    baseline_erosion_rate: float
    protected_erosion_rate: float
    total_reduction_pct: float
    individual_effects: List[PlantProtectionEffect]
    combined_bonus_pct: float
    has_layered_structure: Optional[bool] = False
    layer_combination_type: Optional[str] = None
    wind_speed_attenuation_pct_range: Optional[List[float]] = None
    overall_cohesion_increase_kpa: Optional[float] = None
    model_used: Optional[str] = None
    model_description: Optional[str] = None
