from fastapi import APIRouter, Depends, HTTPException, BackgroundTasks
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, func
from typing import List
from datetime import datetime, timedelta
from ..database import get_db
from ..models.orm import SensorData, WallSegment
from ..models.schemas import SensorDataCreate, SensorData as SensorDataSchema
from ..services.mqtt_alert import mqtt_alert_service

router = APIRouter(prefix="/api/sensor-data", tags=["Sensor Data"])


@router.post("", response_model=SensorDataSchema)
async def create_sensor_data(
    data: SensorDataCreate,
    background_tasks: BackgroundTasks,
    db: AsyncSession = Depends(get_db)
):
    segment = await db.get(WallSegment, data.segment_id)
    if not segment:
        raise HTTPException(status_code=404, detail="Wall segment not found")
    
    db_data = SensorData(**data.model_dump())
    db.add(db_data)
    await db.flush()
    
    background_tasks.add_task(
        mqtt_alert_service.process_sensor_data,
        data.model_dump()
    )
    
    await db.commit()
    await db.refresh(db_data)
    return db_data


@router.post("/batch")
async def create_sensor_data_batch(
    data_list: List[SensorDataCreate],
    background_tasks: BackgroundTasks,
    db: AsyncSession = Depends(get_db)
):
    created = []
    for data in data_list:
        db_data = SensorData(**data.model_dump())
        db.add(db_data)
        created.append(db_data)
        
        background_tasks.add_task(
            mqtt_alert_service.process_sensor_data,
            data.model_dump()
        )
    
    await db.commit()
    for item in created:
        await db.refresh(item)
    
    return {
        "message": f"Successfully created {len(created)} sensor data records",
        "count": len(created),
        "data": created
    }


@router.get("")
async def get_sensor_data(
    segment_id: int = None,
    start_time: datetime = None,
    end_time: datetime = None,
    limit: int = 1000,
    db: AsyncSession = Depends(get_db)
):
    if end_time is None:
        end_time = datetime.now()
    if start_time is None:
        start_time = end_time - timedelta(hours=24)
    
    stmt = select(SensorData).where(
        SensorData.time >= start_time,
        SensorData.time <= end_time
    )
    
    if segment_id is not None:
        stmt = stmt.where(SensorData.segment_id == segment_id)
    
    stmt = stmt.order_by(SensorData.time.desc()).limit(limit)
    result = await db.execute(stmt)
    data = result.scalars().all()
    
    return {
        "start_time": start_time,
        "end_time": end_time,
        "count": len(data),
        "data": list(reversed(data))
    }


@router.get("/latest")
async def get_latest_sensor_data(
    segment_id: int = None,
    db: AsyncSession = Depends(get_db)
):
    stmt = select(SensorData)
    
    if segment_id is not None:
        stmt = stmt.where(SensorData.segment_id == segment_id)
    
    stmt = stmt.order_by(SensorData.time.desc()).limit(1)
    result = await db.execute(stmt)
    data = result.scalars().first()
    
    if not data:
        raise HTTPException(status_code=404, detail="No sensor data found")
    
    return data


@router.get("/statistics")
async def get_sensor_statistics(
    segment_id: int = None,
    start_time: datetime = None,
    end_time: datetime = None,
    db: AsyncSession = Depends(get_db)
):
    if end_time is None:
        end_time = datetime.now()
    if start_time is None:
        start_time = end_time - timedelta(days=7)
    
    stmt = select(
        func.count(SensorData.time).label("count"),
        func.avg(SensorData.wind_erosion_depth).label("avg_erosion_depth"),
        func.max(SensorData.wind_erosion_depth).label("max_erosion_depth"),
        func.avg(SensorData.wind_speed).label("avg_wind_speed"),
        func.max(SensorData.wind_speed).label("max_wind_speed"),
        func.avg(SensorData.soil_moisture).label("avg_soil_moisture"),
        func.avg(SensorData.surface_hardness).label("avg_surface_hardness")
    ).where(
        SensorData.time >= start_time,
        SensorData.time <= end_time
    )
    
    if segment_id is not None:
        stmt = stmt.where(SensorData.segment_id == segment_id)
    
    result = await db.execute(stmt)
    row = result.first()
    
    return {
        "segment_id": segment_id,
        "start_time": start_time,
        "end_time": end_time,
        "total_records": row.count or 0,
        "average_erosion_depth_mm": float(row.avg_erosion_depth or 0),
        "max_erosion_depth_mm": float(row.max_erosion_depth or 0),
        "average_wind_speed_ms": float(row.avg_wind_speed or 0),
        "max_wind_speed_ms": float(row.max_wind_speed or 0),
        "average_soil_moisture_percent": float(row.avg_soil_moisture or 0),
        "average_surface_hardness_mpa": float(row.avg_surface_hardness or 0)
    }
