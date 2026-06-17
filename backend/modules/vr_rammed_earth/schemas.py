from pydantic import BaseModel, Field
from typing import Optional, List, Dict, Any


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
