from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, func
from typing import List
from datetime import datetime, timedelta
from ..database import get_db
from ..models.orm import WallSegment, SensorData, Alert
from ..models.schemas import WallSegment as WallSegmentSchema, WallSegmentCreate, SegmentStatus

router = APIRouter(prefix="/api/wall-segments", tags=["Wall Segments"])


@router.get("", response_model=List[WallSegmentSchema])
async def get_wall_segments(db: AsyncSession = Depends(get_db)):
    stmt = select(WallSegment).order_by(WallSegment.id)
    result = await db.execute(stmt)
    return result.scalars().all()


@router.get("/{segment_id}", response_model=WallSegmentSchema)
async def get_wall_segment(segment_id: int, db: AsyncSession = Depends(get_db)):
    segment = await db.get(WallSegment, segment_id)
    if not segment:
        raise HTTPException(status_code=404, detail="Wall segment not found")
    return segment


@router.post("", response_model=WallSegmentSchema)
async def create_wall_segment(
    segment: WallSegmentCreate,
    db: AsyncSession = Depends(get_db)
):
    db_segment = WallSegment(**segment.model_dump())
    db.add(db_segment)
    await db.commit()
    await db.refresh(db_segment)
    return db_segment


@router.get("/{segment_id}/status", response_model=SegmentStatus)
async def get_segment_status(segment_id: int, db: AsyncSession = Depends(get_db)):
    segment = await db.get(WallSegment, segment_id)
    if not segment:
        raise HTTPException(status_code=404, detail="Wall segment not found")
    
    end_time = datetime.now()
    start_time = end_time - timedelta(hours=24)
    
    stmt = (
        select(SensorData)
        .where(
            SensorData.segment_id == segment_id,
            SensorData.time >= start_time,
            SensorData.time <= end_time
        )
        .order_by(SensorData.time.desc())
    )
    result = await db.execute(stmt)
    sensor_data = result.scalars().all()
    
    if not sensor_data:
        stmt = (
            select(SensorData)
            .where(SensorData.segment_id == segment_id)
            .order_by(SensorData.time.desc())
            .limit(100)
        )
        result = await db.execute(stmt)
        sensor_data = result.scalars().all()
    
    latest_data = sensor_data[0] if sensor_data else None
    
    avg_wind_speed = sum(d.wind_speed for d in sensor_data) / len(sensor_data) if sensor_data else 0
    avg_moisture = sum(d.soil_moisture for d in sensor_data) / len(sensor_data) if sensor_data else 0
    avg_hardness = sum(d.surface_hardness for d in sensor_data) / len(sensor_data) if sensor_data else 0
    
    from ..services.erosion_model import erosion_simulator
    import numpy as np
    
    if len(sensor_data) >= 24:
        wind_speeds = np.array([d.wind_speed for d in sensor_data])
        wind_directions = np.array([d.wind_direction for d in sensor_data])
        hardness = np.array([d.surface_hardness for d in sensor_data])
        moisture = np.array([d.soil_moisture for d in sensor_data])
        
        sim_result = erosion_simulator.calculate_long_term_erosion_rate(
            wind_speeds, wind_directions, hardness, moisture
        )
        erosion_rate = sim_result["erosion_rate_mm_per_year"]
    else:
        erosion_rate = 0.0
    
    stmt = (
        select(func.count(Alert.id))
        .where(
            Alert.segment_id == segment_id,
            Alert.is_acknowledged == False
        )
    )
    result = await db.execute(stmt)
    alert_count = result.scalar() or 0
    
    risk_level = "低"
    if erosion_rate > 0.5 or alert_count > 3:
        risk_level = "高"
    elif erosion_rate > 0.2 or alert_count > 0:
        risk_level = "中"
    
    return SegmentStatus(
        segment_id=segment_id,
        segment_name=segment.name,
        latest_erosion_depth=latest_data.wind_erosion_depth if latest_data else 0,
        erosion_rate=erosion_rate,
        avg_wind_speed_24h=avg_wind_speed,
        avg_soil_moisture_24h=avg_moisture,
        avg_surface_hardness_24h=avg_hardness,
        alert_count=alert_count,
        risk_level=risk_level
    )


@router.get("/{segment_id}/sensor-data")
async def get_segment_sensor_data(
    segment_id: int,
    start_time: datetime = None,
    end_time: datetime = None,
    limit: int = 1000,
    db: AsyncSession = Depends(get_db)
):
    segment = await db.get(WallSegment, segment_id)
    if not segment:
        raise HTTPException(status_code=404, detail="Wall segment not found")
    
    if end_time is None:
        end_time = datetime.now()
    if start_time is None:
        start_time = end_time - timedelta(days=7)
    
    stmt = (
        select(SensorData)
        .where(
            SensorData.segment_id == segment_id,
            SensorData.time >= start_time,
            SensorData.time <= end_time
        )
        .order_by(SensorData.time.desc())
        .limit(limit)
    )
    result = await db.execute(stmt)
    data = result.scalars().all()
    
    return {
        "segment_id": segment_id,
        "segment_name": segment.name,
        "start_time": start_time,
        "end_time": end_time,
        "count": len(data),
        "data": list(reversed(data))
    }
