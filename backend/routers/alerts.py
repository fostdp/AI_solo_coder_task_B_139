from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, func, and_
from typing import List, Optional
from datetime import datetime, timedelta
from ..database import get_db
from ..models.orm import Alert
from ..models.schemas import Alert as AlertSchema, AlertCreate
from ..services.mqtt_alert import mqtt_alert_service

router = APIRouter(prefix="/api/alerts", tags=["Alerts"])


@router.get("", response_model=List[AlertSchema])
async def get_alerts(
    segment_id: int = None,
    alert_type: str = None,
    alert_level: str = None,
    is_acknowledged: bool = None,
    start_time: datetime = None,
    end_time: datetime = None,
    limit: int = 100,
    db: AsyncSession = Depends(get_db)
):
    stmt = select(Alert)
    
    conditions = []
    if segment_id is not None:
        conditions.append(Alert.segment_id == segment_id)
    if alert_type is not None:
        conditions.append(Alert.alert_type == alert_type)
    if alert_level is not None:
        conditions.append(Alert.alert_level == alert_level)
    if is_acknowledged is not None:
        conditions.append(Alert.is_acknowledged == is_acknowledged)
    if start_time is not None:
        conditions.append(Alert.created_at >= start_time)
    if end_time is not None:
        conditions.append(Alert.created_at <= end_time)
    
    if conditions:
        stmt = stmt.where(and_(*conditions))
    
    stmt = stmt.order_by(Alert.created_at.desc()).limit(limit)
    result = await db.execute(stmt)
    return result.scalars().all()


@router.get("/{alert_id}", response_model=AlertSchema)
async def get_alert(alert_id: int, db: AsyncSession = Depends(get_db)):
    alert = await db.get(Alert, alert_id)
    if not alert:
        raise HTTPException(status_code=404, detail="Alert not found")
    return alert


@router.post("", response_model=AlertSchema)
async def create_alert(
    alert: AlertCreate,
    db: AsyncSession = Depends(get_db)
):
    alert_data = alert.model_dump()
    
    mqtt_id = mqtt_alert_service.publish_alert(alert_data)
    
    db_alert = Alert(
        **alert_data,
        mqtt_message_id=mqtt_id
    )
    db.add(db_alert)
    await db.commit()
    await db.refresh(db_alert)
    return db_alert


@router.put("/{alert_id}/acknowledge")
async def acknowledge_alert(
    alert_id: int,
    acknowledged_by: str = "system",
    db: AsyncSession = Depends(get_db)
):
    alert = await db.get(Alert, alert_id)
    if not alert:
        raise HTTPException(status_code=404, detail="Alert not found")
    
    alert.is_acknowledged = True
    alert.acknowledged_at = datetime.now()
    alert.acknowledged_by = acknowledged_by
    
    await db.commit()
    await db.refresh(alert)
    
    return {
        "message": f"Alert {alert_id} acknowledged successfully",
        "alert": alert
    }


@router.get("/summary")
async def get_alerts_summary(
    segment_id: int = None,
    db: AsyncSession = Depends(get_db)
):
    end_time = datetime.now()
    start_time_24h = end_time - timedelta(hours=24)
    start_time_7d = end_time - timedelta(days=7)
    
    base_conditions = []
    if segment_id is not None:
        base_conditions.append(Alert.segment_id == segment_id)
    
    base_stmt = select(func.count(Alert.id))
    if base_conditions:
        base_stmt = base_stmt.where(and_(*base_conditions))
    
    total_active = await db.execute(
        base_stmt.where(Alert.is_acknowledged == False)
    )
    
    total_24h = await db.execute(
        base_stmt.where(Alert.created_at >= start_time_24h)
    )
    
    total_7d = await db.execute(
        base_stmt.where(Alert.created_at >= start_time_7d)
    )
    
    by_level_stmt = select(
        Alert.alert_level,
        func.count(Alert.id).label("count")
    )
    if base_conditions:
        by_level_stmt = by_level_stmt.where(and_(*base_conditions))
    by_level_stmt = by_level_stmt.where(
        Alert.is_acknowledged == False
    ).group_by(Alert.alert_level)
    
    by_level_result = await db.execute(by_level_stmt)
    by_level = {row.alert_level: row.count for row in by_level_result}
    
    by_type_stmt = select(
        Alert.alert_type,
        func.count(Alert.id).label("count")
    )
    if base_conditions:
        by_type_stmt = by_type_stmt.where(and_(*base_conditions))
    by_type_stmt = by_type_stmt.where(
        Alert.is_acknowledged == False
    ).group_by(Alert.alert_type)
    
    by_type_result = await db.execute(by_type_stmt)
    by_type = {row.alert_type: row.count for row in by_type_result}
    
    return {
        "segment_id": segment_id,
        "active_alerts": total_active.scalar() or 0,
        "alerts_last_24h": total_24h.scalar() or 0,
        "alerts_last_7d": total_7d.scalar() or 0,
        "by_level": {
            "critical": by_level.get("critical", 0),
            "danger": by_level.get("danger", 0),
            "warning": by_level.get("warning", 0)
        },
        "by_type": by_type,
        "mqtt_topic": mqtt_alert_service.get_alert_topic(segment_id or 0, "+"),
        "mqtt_connected": mqtt_alert_service.connected
    }


@router.post("/test-mqtt")
async def test_mqtt_alert(
    segment_id: int = 1,
    alert_level: str = "warning",
    db: AsyncSession = Depends(get_db)
):
    test_data = {
        "segment_id": segment_id,
        "segment_name": "测试墙体段",
        "alert_type": "test",
        "alert_level": alert_level,
        "threshold_value": 0.5,
        "measured_value": 0.8,
        "description": "这是一条测试告警消息",
        "timestamp": datetime.now().isoformat(),
        "recommendation": "请确认MQTT消息接收正常"
    }
    
    mqtt_id = mqtt_alert_service.publish_alert(test_data)
    
    if mqtt_id:
        return {
            "success": True,
            "mqtt_message_id": mqtt_id,
            "topic": mqtt_alert_service.get_alert_topic(segment_id, "test"),
            "message": "测试告警已通过MQTT发布"
        }
    else:
        return {
            "success": False,
            "message": "MQTT发布失败，请检查 broker 连接"
        }
