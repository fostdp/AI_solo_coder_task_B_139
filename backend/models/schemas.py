from pydantic import BaseModel, Field
from typing import Optional, List, Dict, Any
from datetime import datetime


class WallSegmentBase(BaseModel):
    name: str
    description: Optional[str] = None
    length_m: float
    height_m: float
    thickness_m: float
    position_start_x: Optional[float] = None
    position_start_y: Optional[float] = None
    position_end_x: Optional[float] = None
    position_end_y: Optional[float] = None
    original_compaction: Optional[float] = None
    construction_year: Optional[int] = None


class WallSegmentCreate(WallSegmentBase):
    pass


class WallSegment(WallSegmentBase):
    id: int
    created_at: datetime

    class Config:
        from_attributes = True


class SensorDataCreate(BaseModel):
    time: datetime
    segment_id: int
    sensor_id: str
    wind_erosion_depth: float = Field(..., description="风蚀深度，单位mm")
    soil_moisture: float = Field(..., description="土体含水量，单位%")
    surface_hardness: float = Field(..., description="表面硬度，单位MPa")
    wind_speed: float = Field(..., description="风速，单位m/s")
    wind_direction: float = Field(..., description="风向，0-360度")
    temperature: Optional[float] = None
    humidity: Optional[float] = None
    dtu_signal_strength: Optional[float] = None


class SensorData(SensorDataCreate):
    created_at: datetime

    class Config:
        from_attributes = True


class ErosionSimulationResult(BaseModel):
    segment_id: int
    simulation_time: datetime
    prediction_period_days: int
    erosion_rate: float
    max_erosion_depth: float
    critical_zones: List[Dict[str, Any]]
    wind_energy: float
    particle_impact_count: float
    model_parameters: Dict[str, Any]


class ErosionSimulationCreate(BaseModel):
    segment_id: int
    prediction_period_days: int = 365


class ReinforcementPlanBase(BaseModel):
    segment_id: int
    plan_name: str
    material_type: str
    material_ratio: Optional[str] = None
    penetration_depth: Optional[float] = None
    cost_per_sqm: float
    construction_difficulty: Optional[int] = None
    durability_years: Optional[float] = None
    durability_confidence: Optional[float] = None
    durability_lower_bound: Optional[float] = None
    durability_upper_bound: Optional[float] = None
    environmental_impact: Optional[float] = None
    aging_test_data: Optional[List[Dict[str, Any]]] = None
    acceleration_factors: Optional[Dict[str, Any]] = None


class ReinforcementPlanCreate(ReinforcementPlanBase):
    pass


class ReinforcementPlan(ReinforcementPlanBase):
    id: int
    topsis_score: Optional[float] = None
    topsis_rank: Optional[int] = None
    is_selected: bool
    created_at: datetime

    class Config:
        from_attributes = True


class TOPSISEvaluationRequest(BaseModel):
    segment_id: int
    weights: Dict[str, float] = Field(
        default_factory=lambda: {
            "penetration_depth": 0.25,
            "durability_years": 0.25,
            "durability_confidence": 0.10,
            "cost_per_sqm": 0.20,
            "construction_difficulty": 0.10,
            "environmental_impact": 0.10
        }
    )
    benefit_criteria: List[str] = Field(
        default_factory=lambda: ["penetration_depth", "durability_years", "durability_confidence"]
    )
    cost_criteria: List[str] = Field(
        default_factory=lambda: ["cost_per_sqm", "construction_difficulty", "environmental_impact"]
    )


class TOPSISEvaluationResult(BaseModel):
    plan_id: int
    plan_name: str
    material_type: str
    topsis_score: float
    topsis_rank: int
    criteria_scores: Dict[str, float]
    is_selected: bool


class AlertCreate(BaseModel):
    segment_id: int
    alert_type: str
    alert_level: str
    threshold_value: Optional[float] = None
    measured_value: Optional[float] = None
    description: Optional[str] = None


class Alert(AlertCreate):
    id: int
    mqtt_message_id: Optional[str] = None
    is_acknowledged: bool
    acknowledged_at: Optional[datetime] = None
    acknowledged_by: Optional[str] = None
    created_at: datetime

    class Config:
        from_attributes = True


class CrackDataCreate(BaseModel):
    time: datetime
    segment_id: int
    crack_id: str
    crack_width: float
    crack_length: Optional[float] = None
    crack_depth: Optional[float] = None
    extension_rate: Optional[float] = None
    location_x: Optional[float] = None
    location_y: Optional[float] = None


class WindFieldData(BaseModel):
    time: datetime
    grid_x: int
    grid_y: int
    grid_z: int
    velocity_x: float
    velocity_y: float
    velocity_z: float
    wind_speed: float
    wind_direction: float
    turbulence_intensity: Optional[float] = None
    particle_concentration: Optional[float] = None


class ErosionPredictionRequest(BaseModel):
    segment_id: int
    prediction_years: float = 5.0
    wind_speed_avg: Optional[float] = None
    wind_direction_avg: Optional[float] = None
    include_critical_zones: bool = True


class ErosionPredictionResponse(BaseModel):
    segment_id: int
    segment_name: str
    current_erosion_rate: float
    predicted_erosion_rate: float
    predicted_max_depth: float
    prediction_years: float
    risk_level: str
    critical_zones: List[Dict[str, Any]]
    recommendation: str


class StatisticsResponse(BaseModel):
    total_segments: int
    total_sensor_data: int
    active_alerts: int
    avg_erosion_rate: float
    max_erosion_rate: float
    avg_wind_speed: float
    avg_soil_moisture: float
    avg_surface_hardness: float


class SegmentStatus(BaseModel):
    segment_id: int
    segment_name: str
    latest_erosion_depth: float
    erosion_rate: float
    avg_wind_speed_24h: float
    avg_soil_moisture_24h: float
    avg_surface_hardness_24h: float
    alert_count: int
    risk_level: str
