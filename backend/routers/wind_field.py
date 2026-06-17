from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, func
from typing import List
from datetime import datetime, timedelta
from ..database import get_db
from ..models.orm import WindFieldSnapshot, SensorData
from ..models.schemas import WindFieldData
from ..services.erosion_model import erosion_simulator

router = APIRouter(prefix="/api/wind-field", tags=["Wind Field"])


@router.post("/generate")
async def generate_wind_field(
    wind_speed: float,
    wind_direction: float,
    grid_size_x: int = 10,
    grid_size_y: int = 5,
    grid_size_z: int = 5,
    x_min: float = 0,
    x_max: float = 10,
    y_min: float = 0,
    y_max: float = 5,
    z_min: float = 0,
    z_max: float = 3,
    db: AsyncSession = Depends(get_db)
):
    bounds = (x_min, x_max, y_min, y_max, z_min, z_max)
    grid_size = (grid_size_x, grid_size_y, grid_size_z)
    
    field_data = erosion_simulator.generate_wind_field(
        wind_speed, wind_direction, grid_size, bounds
    )
    
    for point in field_data:
        snapshot = WindFieldSnapshot(
            time=point["time"],
            grid_x=point["grid_x"],
            grid_y=point["grid_y"],
            grid_z=point["grid_z"],
            velocity_x=point["velocity_x"],
            velocity_y=point["velocity_y"],
            velocity_z=point["velocity_z"],
            wind_speed=point["wind_speed"],
            wind_direction=point["wind_direction"],
            turbulence_intensity=point["turbulence_intensity"],
            particle_concentration=point["particle_concentration"]
        )
        db.add(snapshot)
    
    await db.commit()
    
    return {
        "grid_size": grid_size,
        "bounds": bounds,
        "wind_speed": wind_speed,
        "wind_direction": wind_direction,
        "total_points": len(field_data),
        "generated_at": datetime.now(),
        "field_data": field_data
    }


@router.get("/latest")
async def get_latest_wind_field(
    segment_id: int = None,
    db: AsyncSession = Depends(get_db)
):
    if segment_id is not None:
        stmt = (
            select(SensorData)
            .where(SensorData.segment_id == segment_id)
            .order_by(SensorData.time.desc())
            .limit(10)
        )
        result = await db.execute(stmt)
        sensor_data = result.scalars().all()
        
        if sensor_data:
            avg_wind_speed = sum(d.wind_speed for d in sensor_data) / len(sensor_data)
            avg_wind_direction = sum(d.wind_direction for d in sensor_data) / len(sensor_data)
        else:
            avg_wind_speed = 5.0
            avg_wind_direction = 180.0
    else:
        avg_wind_speed = 5.0
        avg_wind_direction = 180.0
    
    field_data = erosion_simulator.generate_wind_field(
        avg_wind_speed, avg_wind_direction
    )
    
    return {
        "segment_id": segment_id,
        "avg_wind_speed": avg_wind_speed,
        "avg_wind_direction": avg_wind_direction,
        "grid_size": (10, 5, 5),
        "bounds": (0, 10, 0, 5, 0, 3),
        "field_data": field_data
    }


@router.get("/snapshots")
async def get_wind_field_snapshots(
    start_time: datetime = None,
    end_time: datetime = None,
    limit: int = 1000,
    db: AsyncSession = Depends(get_db)
):
    if end_time is None:
        end_time = datetime.now()
    if start_time is None:
        start_time = end_time - timedelta(hours=1)
    
    stmt = (
        select(WindFieldSnapshot)
        .where(
            WindFieldSnapshot.time >= start_time,
            WindFieldSnapshot.time <= end_time
        )
        .order_by(WindFieldSnapshot.time.desc())
        .limit(limit)
    )
    result = await db.execute(stmt)
    snapshots = result.scalars().all()
    
    return {
        "start_time": start_time,
        "end_time": end_time,
        "count": len(snapshots),
        "snapshots": snapshots
    }


@router.get("/streamlines")
async def get_wind_streamlines(
    wind_speed: float = 5.0,
    wind_direction: float = 180.0,
    num_particles: int = 100,
    integration_steps: int = 50,
    step_size: float = 0.1
):
    import numpy as np
    
    bounds = np.array([[0, 10], [0, 5], [0, 3]])
    particles = np.random.rand(num_particles, 3) * (bounds[:, 1] - bounds[:, 0]) + bounds[:, 0]
    
    wind_direction_rad = np.radians(wind_direction)
    base_velocity = np.array([
        wind_speed * np.sin(wind_direction_rad),
        wind_speed * np.cos(wind_direction_rad),
        wind_speed * 0.05
    ])
    
    streamlines = []
    
    for p_idx in range(num_particles):
        positions = [particles[p_idx].tolist()]
        pos = particles[p_idx].copy()
        
        for step in range(integration_steps):
            height_factor = np.log(pos[2] + 0.001) / np.log(2.0 + 0.001)
            height_factor = max(0.1, min(1.5, height_factor))
            
            turbulence = np.random.normal(0, wind_speed * 0.1, 3)
            velocity = base_velocity * height_factor + turbulence
            
            pos += velocity * step_size
            
            pos = np.clip(pos, bounds[:, 0], bounds[:, 1])
            
            if step % 2 == 0:
                positions.append(pos.tolist())
        
        streamlines.append({
            "particle_id": p_idx,
            "positions": positions,
            "speed": np.linalg.norm(base_velocity),
            "lifetime": integration_steps * step_size
        })
    
    return {
        "wind_speed": wind_speed,
        "wind_direction": wind_direction,
        "num_particles": num_particles,
        "integration_steps": integration_steps,
        "step_size": step_size,
        "bounds": bounds.tolist(),
        "streamlines": streamlines
    }


@router.post("/crack")
async def create_crack_data(
    crack_data: dict,
    db: AsyncSession = Depends(get_db)
):
    from ..models.orm import CrackMonitoring
    from ..models.schemas import CrackDataCreate
    
    try:
        crack_create = CrackDataCreate(**crack_data)
    except Exception as e:
        raise HTTPException(status_code=400, detail=f"Invalid crack data: {e}")
    
    db_crack = CrackMonitoring(**crack_create.model_dump())
    db.add(db_crack)
    
    from ..services.mqtt_alert import mqtt_alert_service
    alert = await mqtt_alert_service.check_crack_alert(
        db, crack_create.segment_id, crack_create.model_dump()
    )
    
    await db.commit()
    await db.refresh(db_crack)
    
    return {
        "crack_data": db_crack,
        "alert_generated": alert is not None,
        "alert": alert
    }
