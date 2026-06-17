from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from typing import List
from datetime import datetime, timedelta
from ..database import get_db
from ..models.orm import ErosionSimulation, WallSegment, SensorData
from ..models.schemas import (
    ErosionPredictionRequest,
    ErosionPredictionResponse,
    ErosionSimulationResult
)
from ..services.erosion_model import erosion_simulator
import numpy as np

router = APIRouter(prefix="/api/erosion", tags=["Erosion Simulation"])


@router.post("/predict", response_model=ErosionPredictionResponse)
async def predict_erosion(
    request: ErosionPredictionRequest,
    db: AsyncSession = Depends(get_db)
):
    try:
        result = await erosion_simulator.get_segment_erosion_prediction(
            db,
            request.segment_id,
            request.prediction_years,
            request.wind_speed_avg,
            request.wind_direction_avg,
            request.include_critical_zones
        )
        await db.commit()
        return result
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/simulate")
async def simulate_erosion(
    segment_id: int,
    prediction_period_days: int = 365,
    db: AsyncSession = Depends(get_db)
):
    segment = await db.get(WallSegment, segment_id)
    if not segment:
        raise HTTPException(status_code=404, detail="Wall segment not found")
    
    end_time = datetime.now()
    start_time = end_time - timedelta(days=min(30, prediction_period_days))
    
    stmt = (
        select(SensorData)
        .where(
            SensorData.segment_id == segment_id,
            SensorData.time >= start_time,
            SensorData.time <= end_time
        )
        .order_by(SensorData.time)
    )
    result = await db.execute(stmt)
    sensor_data = result.scalars().all()
    
    if len(sensor_data) < 24:
        raise HTTPException(
            status_code=400,
            detail="Insufficient sensor data for simulation. Need at least 24 hours of data."
        )
    
    wind_speeds = np.array([d.wind_speed for d in sensor_data])
    wind_directions = np.array([d.wind_direction for d in sensor_data])
    surface_hardness = np.array([d.surface_hardness for d in sensor_data])
    soil_moisture = np.array([d.soil_moisture for d in sensor_data])
    
    simulation_result = erosion_simulator.calculate_long_term_erosion_rate(
        wind_speeds, wind_directions, surface_hardness, soil_moisture
    )
    
    sim_record = ErosionSimulation(
        segment_id=segment_id,
        simulation_time=datetime.now(),
        prediction_period_days=prediction_period_days,
        erosion_rate=simulation_result["erosion_rate_mm_per_year"],
        max_erosion_depth=simulation_result["max_erosion_depth_mm"],
        critical_zones=simulation_result["critical_zones"],
        wind_energy=simulation_result["total_wind_energy"],
        particle_impact_count=simulation_result["total_particle_count"],
        model_parameters={
            "data_points": len(sensor_data),
            "time_span_hours": len(sensor_data),
            "air_density": erosion_simulator.AIR_DENSITY,
            "sand_density": erosion_simulator.SAND_DENSITY
        }
    )
    db.add(sim_record)
    await db.commit()
    await db.refresh(sim_record)
    
    return {
        "segment_id": segment_id,
        "segment_name": segment.name,
        "simulation_id": sim_record.id,
        "simulation_time": sim_record.simulation_time,
        "prediction_period_days": prediction_period_days,
        "erosion_rate_mm_per_year": simulation_result["erosion_rate_mm_per_year"],
        "total_erosion_mm": simulation_result["total_erosion_mm"],
        "max_erosion_depth_mm": simulation_result["max_erosion_depth_mm"],
        "avg_erosion_depth_mm": simulation_result["avg_erosion_depth_mm"],
        "total_wind_energy": simulation_result["total_wind_energy"],
        "total_particle_impacts": simulation_result["total_particle_count"],
        "critical_zones": simulation_result["critical_zones"],
        "erosion_events": simulation_result["erosion_events"][:20]
    }


@router.get("/simulations")
async def get_erosion_simulations(
    segment_id: int = None,
    limit: int = 100,
    db: AsyncSession = Depends(get_db)
):
    stmt = select(ErosionSimulation)
    
    if segment_id is not None:
        stmt = stmt.where(ErosionSimulation.segment_id == segment_id)
    
    stmt = stmt.order_by(ErosionSimulation.simulation_time.desc()).limit(limit)
    result = await db.execute(stmt)
    simulations = result.scalars().all()
    
    return {
        "count": len(simulations),
        "simulations": simulations
    }


@router.get("/simulations/{simulation_id}")
async def get_erosion_simulation(
    simulation_id: int,
    db: AsyncSession = Depends(get_db)
):
    simulation = await db.get(ErosionSimulation, simulation_id)
    if not simulation:
        raise HTTPException(status_code=404, detail="Simulation not found")
    return simulation


@router.post("/two-phase-flow")
async def simulate_two_phase_flow(
    wind_speed: float,
    wind_direction: float,
    surface_hardness: float,
    soil_moisture: float,
    duration_hours: float = 1.0
):
    result = erosion_simulator.simulate_two_phase_flow(
        wind_speed, wind_direction, surface_hardness, soil_moisture, duration_hours
    )
    return result
