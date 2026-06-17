from pydantic import BaseModel, Field
from typing import Optional, List, Dict, Any


class DynastyCraftParams(BaseModel):
    dynasty_code: str
    name: str
    period: str
    compaction_ratio: float
    binder_type: str
    binder_ratio: float
    hardness_multiplier: float
    erosion_rate_modifier: float
    surface_cohesion_kpa: float
    moisture_resistance: float


class DynastyComparisonRequest(BaseModel):
    dynasty_codes: List[str] = ["QIN", "HAN", "MING"]
    wind_speed: float = 8.0
    soil_moisture: float = 5.0
    duration_hours: float = 24.0
    climate_scenario: Optional[str] = None


class DynastyComparisonResult(BaseModel):
    dynasty_code: str
    name: str
    erosion_rate_mm_per_year: float
    max_erosion_depth_mm: float
    hardness_mpa: float
    cohesion_kpa: float
    moisture_resistance: float
    overall_score: float
    rank: int


class DynastyComparisonResponse(BaseModel):
    request: DynastyComparisonRequest
    results: List[DynastyComparisonResult]
    climate_scenario: Dict[str, Any]


class CrossEraComparisonRequest(BaseModel):
    include_dynasties: List[str] = ["QIN", "HAN", "MING"]
    include_modern: List[str] = ["GEOSYNTHETIC", "FIBER", "CEMENT"]
    wind_speed: float = 8.0
    soil_moisture: float = 5.0


class CrossEraItem(BaseModel):
    code: str
    name: str
    era: str
    erosion_rate_mm_per_year: float
    hardness_mpa: float
    cohesion_kpa: float
    environmental_impact: float
    reversibility: float
    cultural_authenticity: float
    topsis_score: Optional[float] = None


class CrossEraComparisonResponse(BaseModel):
    items: List[CrossEraItem]
    ranking: List[Dict[str, Any]]


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
    soil_cohesion_increase_kpa: float
    wind_speed_reduction_pct: float
    erosion_rate_reduction_pct: float
    moisture_retention_pct: float
    surface_binding: float


class PlantRootSimulationResponse(BaseModel):
    request: PlantRootSimulationRequest
    baseline_erosion_rate: float
    protected_erosion_rate: float
    total_reduction_pct: float
    individual_effects: List[PlantProtectionEffect]
    combined_bonus_pct: float


class MaterialMix(BaseModel):
    soil_pct: float = 65
    clay_pct: float = 15
    sand_pct: float = 10
    lime_pct: float = 3
    rice_paste_pct: float = 2
    straw_pct: float = 1
    water_pct: float = 16


class VirtualExperienceRequest(BaseModel):
    mix: MaterialMix
    tamping_preset: str = "heavy"
    wall_height_m: float = 2.5
    wind_speed: float = 8.0


class VirtualExperienceResponse(BaseModel):
    mix: MaterialMix
    tamping_preset: str
    compaction_ratio: float
    quality_score: float
    quality_rating: str
    quality_color: str
    erosion_rate_mm_per_year: float
    hardness_mpa: float
    cohesion_kpa: float
    crack_resistance: float
    moisture_resistance: float
    dynasty_match: str
    dynasty_match_score: float
    suggestions: List[str]
