from sqlalchemy import Column, Integer, String, Float, DateTime, Boolean, ForeignKey, JSON, Index
from sqlalchemy.sql import func
from ..database import Base


class WallSegment(Base):
    __tablename__ = "wall_segments"

    id = Column(Integer, primary_key=True, index=True)
    name = Column(String(100), nullable=False)
    description = Column(String(1000))
    length_m = Column(Float, nullable=False)
    height_m = Column(Float, nullable=False)
    thickness_m = Column(Float, nullable=False)
    position_start_x = Column(Float)
    position_start_y = Column(Float)
    position_end_x = Column(Float)
    position_end_y = Column(Float)
    original_compaction = Column(Float)
    construction_year = Column(Integer)
    created_at = Column(DateTime(timezone=True), server_default=func.now())


class SensorData(Base):
    __tablename__ = "sensor_data"

    time = Column(DateTime(timezone=True), primary_key=True)
    segment_id = Column(Integer, ForeignKey("wall_segments.id"), primary_key=True)
    sensor_id = Column(String(50), nullable=False)
    wind_erosion_depth = Column(Float, nullable=False)
    soil_moisture = Column(Float, nullable=False)
    surface_hardness = Column(Float, nullable=False)
    wind_speed = Column(Float, nullable=False)
    wind_direction = Column(Float, nullable=False)
    temperature = Column(Float)
    humidity = Column(Float)
    dtu_signal_strength = Column(Float)
    created_at = Column(DateTime(timezone=True), server_default=func.now())

    __table_args__ = (
        Index("idx_sensor_data_segment_time", "segment_id", "time", postgresql_using="btree"),
        Index("idx_sensor_data_sensor_time", "sensor_id", "time", postgresql_using="btree"),
    )


class ErosionSimulation(Base):
    __tablename__ = "erosion_simulation"

    id = Column(Integer, primary_key=True)
    segment_id = Column(Integer, ForeignKey("wall_segments.id"), nullable=False)
    simulation_time = Column(DateTime(timezone=True), nullable=False)
    prediction_period_days = Column(Integer, nullable=False)
    erosion_rate = Column(Float, nullable=False)
    max_erosion_depth = Column(Float, nullable=False)
    critical_zones = Column(JSON)
    wind_energy = Column(Float)
    particle_impact_count = Column(Float)
    model_parameters = Column(JSON)
    created_at = Column(DateTime(timezone=True), server_default=func.now())


class ReinforcementPlan(Base):
    __tablename__ = "reinforcement_plans"

    id = Column(Integer, primary_key=True)
    segment_id = Column(Integer, ForeignKey("wall_segments.id"), nullable=False)
    plan_name = Column(String(100), nullable=False)
    material_type = Column(String(50), nullable=False)
    material_ratio = Column(String(100))
    penetration_depth = Column(Float)
    cost_per_sqm = Column(Float, nullable=False)
    construction_difficulty = Column(Integer)
    durability_years = Column(Float)
    durability_confidence = Column(Float)
    durability_lower_bound = Column(Float)
    durability_upper_bound = Column(Float)
    environmental_impact = Column(Float)
    acceleration_factor = Column(Float)
    aging_test_days = Column(Integer)
    strength_retention = Column(Float)
    topsis_score = Column(Float)
    topsis_rank = Column(Integer)
    is_selected = Column(Boolean, default=False)
    created_at = Column(DateTime(timezone=True), server_default=func.now())


class ReinforcementMaterial(Base):
    __tablename__ = "reinforcement_materials"

    id = Column(Integer, primary_key=True)
    material_name = Column(String(100), nullable=False)
    material_code = Column(String(50), unique=True, nullable=False)
    description = Column(String(1000))
    penetration_coefficient = Column(Float)
    bonding_strength = Column(Float)
    cost_per_kg = Column(Float)
    application_method = Column(String(100))
    created_at = Column(DateTime(timezone=True), server_default=func.now())


class Alert(Base):
    __tablename__ = "alerts"

    id = Column(Integer, primary_key=True)
    segment_id = Column(Integer, ForeignKey("wall_segments.id"), nullable=False)
    alert_type = Column(String(50), nullable=False)
    alert_level = Column(String(20), nullable=False)
    threshold_value = Column(Float)
    measured_value = Column(Float)
    description = Column(String(1000))
    mqtt_message_id = Column(String(100))
    is_acknowledged = Column(Boolean, default=False)
    acknowledged_at = Column(DateTime(timezone=True))
    acknowledged_by = Column(String(100))
    created_at = Column(DateTime(timezone=True), server_default=func.now())


class CrackMonitoring(Base):
    __tablename__ = "crack_monitoring"

    time = Column(DateTime(timezone=True), primary_key=True)
    segment_id = Column(Integer, ForeignKey("wall_segments.id"), primary_key=True)
    crack_id = Column(String(50), nullable=False)
    crack_width = Column(Float, nullable=False)
    crack_length = Column(Float)
    crack_depth = Column(Float)
    extension_rate = Column(Float)
    location_x = Column(Float)
    location_y = Column(Float)
    created_at = Column(DateTime(timezone=True), server_default=func.now())


class WindFieldSnapshot(Base):
    __tablename__ = "wind_field_snapshots"

    time = Column(DateTime(timezone=True), primary_key=True)
    grid_x = Column(Integer, primary_key=True)
    grid_y = Column(Integer, primary_key=True)
    grid_z = Column(Integer, primary_key=True)
    velocity_x = Column(Float)
    velocity_y = Column(Float)
    velocity_z = Column(Float)
    wind_speed = Column(Float)
    wind_direction = Column(Float)
    turbulence_intensity = Column(Float)
    particle_concentration = Column(Float)
    created_at = Column(DateTime(timezone=True), server_default=func.now())
