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
