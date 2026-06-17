from pydantic import BaseModel, Field
from typing import Optional, List, Dict, Any


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
