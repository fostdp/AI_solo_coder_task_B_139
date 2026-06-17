from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, func
from datetime import datetime, timedelta
from ..database import get_db
from ..models.orm import WallSegment, SensorData, Alert
from ..models.schemas import StatisticsResponse, SegmentStatus
from typing import List
import numpy as np

router = APIRouter(prefix="/api/statistics", tags=["Statistics"])


@router.get("", response_model=StatisticsResponse)
async def get_overall_statistics(db: AsyncSession = Depends(get_db)):
    end_time = datetime.now()
    start_time = end_time - timedelta(days=30)
    
    total_segments_stmt = select(func.count(WallSegment.id))
    total_segments_result = await db.execute(total_segments_stmt)
    total_segments = total_segments_result.scalar() or 0
    
    total_sensor_data_stmt = select(func.count(SensorData.time))
    total_sensor_data_result = await db.execute(total_sensor_data_stmt)
    total_sensor_data = total_sensor_data_result.scalar() or 0
    
    active_alerts_stmt = select(func.count(Alert.id)).where(
        Alert.is_acknowledged == False
    )
    active_alerts_result = await db.execute(active_alerts_stmt)
    active_alerts = active_alerts_result.scalar() or 0
    
    recent_data_stmt = (
        select(SensorData)
        .where(SensorData.time >= start_time)
        .order_by(SensorData.time.desc())
        .limit(10000)
    )
    recent_data_result = await db.execute(recent_data_stmt)
    recent_data = recent_data_result.scalars().all()
    
    if recent_data:
        from ..services.erosion_model import erosion_simulator
        
        wind_speeds = np.array([d.wind_speed for d in recent_data])
        wind_directions = np.array([d.wind_direction for d in recent_data])
        hardness = np.array([d.surface_hardness for d in recent_data])
        moisture = np.array([d.soil_moisture for d in recent_data])
        
        sim_result = erosion_simulator.calculate_long_term_erosion_rate(
            wind_speeds, wind_directions, hardness, moisture
        )
        
        avg_erosion_rate = sim_result["erosion_rate_mm_per_year"]
        max_erosion_rate = sim_result["max_erosion_depth_mm"]
        avg_wind_speed = float(np.mean(wind_speeds))
        avg_soil_moisture = float(np.mean(moisture))
        avg_surface_hardness = float(np.mean(hardness))
    else:
        avg_erosion_rate = 0.0
        max_erosion_rate = 0.0
        avg_wind_speed = 0.0
        avg_soil_moisture = 0.0
        avg_surface_hardness = 0.0
    
    return StatisticsResponse(
        total_segments=total_segments,
        total_sensor_data=total_sensor_data,
        active_alerts=active_alerts,
        avg_erosion_rate=avg_erosion_rate,
        max_erosion_rate=max_erosion_rate,
        avg_wind_speed=avg_wind_speed,
        avg_soil_moisture=avg_soil_moisture,
        avg_surface_hardness=avg_surface_hardness
    )


@router.get("/all-segments-status", response_model=List[SegmentStatus])
async def get_all_segments_status(db: AsyncSession = Depends(get_db)):
    segments_stmt = select(WallSegment).order_by(WallSegment.id)
    segments_result = await db.execute(segments_stmt)
    segments = segments_result.scalars().all()
    
    status_list = []
    end_time = datetime.now()
    start_time = end_time - timedelta(hours=24)
    
    for segment in segments:
        data_stmt = (
            select(SensorData)
            .where(
                SensorData.segment_id == segment.id,
                SensorData.time >= start_time,
                SensorData.time <= end_time
            )
            .order_by(SensorData.time.desc())
        )
        data_result = await db.execute(data_stmt)
        sensor_data = data_result.scalars().all()
        
        if not sensor_data:
            data_stmt = (
                select(SensorData)
                .where(SensorData.segment_id == segment.id)
                .order_by(SensorData.time.desc())
                .limit(100)
            )
            data_result = await db.execute(data_stmt)
            sensor_data = data_result.scalars().all()
        
        latest_data = sensor_data[0] if sensor_data else None
        
        avg_wind_speed = sum(d.wind_speed for d in sensor_data) / len(sensor_data) if sensor_data else 0
        avg_moisture = sum(d.soil_moisture for d in sensor_data) / len(sensor_data) if sensor_data else 0
        avg_hardness = sum(d.surface_hardness for d in sensor_data) / len(sensor_data) if sensor_data else 0
        
        from ..services.erosion_model import erosion_simulator
        
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
        
        alert_stmt = select(func.count(Alert.id)).where(
            Alert.segment_id == segment.id,
            Alert.is_acknowledged == False
        )
        alert_result = await db.execute(alert_stmt)
        alert_count = alert_result.scalar() or 0
        
        risk_level = "低"
        if erosion_rate > 0.5 or alert_count > 3:
            risk_level = "高"
        elif erosion_rate > 0.2 or alert_count > 0:
            risk_level = "中"
        
        status_list.append(SegmentStatus(
            segment_id=segment.id,
            segment_name=segment.name,
            latest_erosion_depth=latest_data.wind_erosion_depth if latest_data else 0,
            erosion_rate=erosion_rate,
            avg_wind_speed_24h=avg_wind_speed,
            avg_soil_moisture_24h=avg_moisture,
            avg_surface_hardness_24h=avg_hardness,
            alert_count=alert_count,
            risk_level=risk_level
        ))
    
    return status_list


@router.get("/erosion-trend")
async def get_erosion_trend(
    segment_id: int = None,
    days: int = 30,
    db: AsyncSession = Depends(get_db)
):
    end_time = datetime.now()
    start_time = end_time - timedelta(days=days)
    
    stmt = (
        select(
            func.date_trunc('day', SensorData.time).label('day'),
            func.avg(SensorData.wind_erosion_depth).label('avg_erosion'),
            func.max(SensorData.wind_erosion_depth).label('max_erosion'),
            func.avg(SensorData.wind_speed).label('avg_wind_speed'),
            func.count(SensorData.time).label('data_points')
        )
        .where(
            SensorData.time >= start_time,
            SensorData.time <= end_time
        )
    )
    
    if segment_id is not None:
        stmt = stmt.where(SensorData.segment_id == segment_id)
    
    stmt = stmt.group_by(func.date_trunc('day', SensorData.time)).order_by('day')
    result = await db.execute(stmt)
    rows = result.all()
    
    trend_data = []
    for row in rows:
        trend_data.append({
            "date": row.day.strftime("%Y-%m-%d"),
            "avg_erosion_depth_mm": float(row.avg_erosion or 0),
            "max_erosion_depth_mm": float(row.max_erosion or 0),
            "avg_wind_speed_ms": float(row.avg_wind_speed or 0),
            "data_points": int(row.data_points or 0)
        })
    
    return {
        "segment_id": segment_id,
        "start_date": start_time.strftime("%Y-%m-%d"),
        "end_date": end_time.strftime("%Y-%m-%d"),
        "days": days,
        "trend_data": trend_data
    }


@router.get("/dashboard")
async def get_dashboard_data(db: AsyncSession = Depends(get_db)):
    overall_stats = await get_overall_statistics(db)
    segments_status = await get_all_segments_status(db)
    
    high_risk_segments = [s for s in segments_status if s.risk_level == "高"]
    medium_risk_segments = [s for s in segments_status if s.risk_level == "中"]
    low_risk_segments = [s for s in segments_status if s.risk_level == "低"]
    
    end_time = datetime.now()
    start_time = end_time - timedelta(hours=1)
    
    recent_sensor_stmt = (
        select(SensorData)
        .where(SensorData.time >= start_time)
        .order_by(SensorData.time.desc())
        .limit(10)
    )
    recent_sensor_result = await db.execute(recent_sensor_stmt)
    recent_sensor_data = recent_sensor_result.scalars().all()
    
    recent_alerts_stmt = (
        select(Alert)
        .order_by(Alert.created_at.desc())
        .limit(10)
    )
    recent_alerts_result = await db.execute(recent_alerts_stmt)
    recent_alerts = recent_alerts_result.scalars().all()
    
    avg_erosion_by_segment = []
    for status in segments_status:
        avg_erosion_by_segment.append({
            "segment_id": status.segment_id,
            "segment_name": status.segment_name,
            "erosion_rate": status.erosion_rate,
            "risk_level": status.risk_level
        })
    
    return {
        "overview": {
            "total_segments": overall_stats.total_segments,
            "total_sensor_data": overall_stats.total_sensor_data,
            "active_alerts": overall_stats.active_alerts,
            "avg_erosion_rate": overall_stats.avg_erosion_rate,
            "avg_wind_speed": overall_stats.avg_wind_speed
        },
        "risk_distribution": {
            "high": len(high_risk_segments),
            "medium": len(medium_risk_segments),
            "low": len(low_risk_segments)
        },
        "high_risk_segments": high_risk_segments,
        "erosion_rate_by_segment": avg_erosion_by_segment,
        "recent_sensor_data": list(recent_sensor_data),
        "recent_alerts": list(recent_alerts)
    }
