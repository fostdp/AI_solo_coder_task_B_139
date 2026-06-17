import json
import uuid
import asyncio
import logging
from datetime import datetime
from typing import Optional, Dict, Any
import paho.mqtt.client as mqtt
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from ..models.orm import Alert, WallSegment, SensorData, CrackMonitoring
from ..models.schemas import AlertCreate
from ..config import settings
from ..database import AsyncSessionLocal

logger = logging.getLogger(__name__)


class MQTTAlertService:
    def __init__(self):
        self.client: Optional[mqtt.Client] = None
        self.connected = False
        self.erosion_threshold = settings.EROSION_THRESHOLD
        self.crack_threshold = settings.CRACK_THRESHOLD
        self._connect_lock = asyncio.Lock()

    def connect(self) -> bool:
        try:
            self.client = mqtt.Client(
                client_id=f"{settings.MQTT_CLIENT_ID}_{uuid.uuid4().hex[:8]}",
                protocol=mqtt.MQTTv5
            )
            
            if settings.MQTT_USERNAME and settings.MQTT_PASSWORD:
                self.client.username_pw_set(settings.MQTT_USERNAME, settings.MQTT_PASSWORD)
            
            self.client.on_connect = self._on_connect
            self.client.on_disconnect = self._on_disconnect
            self.client.on_publish = self._on_publish
            
            self.client.connect(
                settings.MQTT_BROKER,
                settings.MQTT_PORT,
                keepalive=60
            )
            
            self.client.loop_start()
            return True
        except Exception as e:
            logger.error(f"Failed to connect to MQTT broker: {e}")
            return False

    def _on_connect(self, client, userdata, flags, rc, properties=None):
        if rc == 0:
            self.connected = True
            logger.info("Connected to MQTT broker successfully")
        else:
            self.connected = False
            logger.error(f"Failed to connect to MQTT broker, code: {rc}")

    def _on_disconnect(self, client, userdata, rc, properties=None):
        self.connected = False
        logger.warning(f"Disconnected from MQTT broker, code: {rc}")

    def _on_publish(self, client, userdata, mid, reason_code=None, properties=None):
        logger.debug(f"Message published with MID: {mid}")

    def disconnect(self):
        if self.client:
            self.client.loop_stop()
            self.client.disconnect()
            self.connected = False

    def publish_alert(self, alert_data: Dict[str, Any]) -> Optional[str]:
        if not self.connected:
            if not self.connect():
                logger.warning("Cannot publish alert: MQTT not connected")
                return None
        
        message_id = str(uuid.uuid4())
        alert_data["mqtt_message_id"] = message_id
        alert_data["published_at"] = datetime.now().isoformat()
        
        try:
            topic = f"{settings.MQTT_TOPIC}/{alert_data.get('segment_id', 'unknown')}/{alert_data.get('alert_type', 'unknown')}"
            payload = json.dumps(alert_data, ensure_ascii=False)
            
            result = self.client.publish(
                topic,
                payload=payload,
                qos=1,
                retain=False
            )
            
            if result.rc == mqtt.MQTT_ERR_SUCCESS:
                logger.info(f"Alert published to {topic}, MID: {result.mid}")
                return message_id
            else:
                logger.error(f"Failed to publish alert, code: {result.rc}")
                return None
        except Exception as e:
            logger.error(f"Error publishing alert: {e}")
            return None

    async def check_erosion_alert(
        self,
        db: AsyncSession,
        segment_id: int,
        erosion_rate: float
    ) -> Optional[Alert]:
        if erosion_rate <= self.erosion_threshold:
            return None
        
        segment = await db.get(WallSegment, segment_id)
        if not segment:
            return None
        
        alert_level = "warning"
        if erosion_rate > self.erosion_threshold * 2:
            alert_level = "critical"
        elif erosion_rate > self.erosion_threshold * 1.5:
            alert_level = "danger"
        
        alert_data = {
            "segment_id": segment_id,
            "segment_name": segment.name,
            "alert_type": "erosion_rate",
            "alert_level": alert_level,
            "threshold_value": self.erosion_threshold,
            "measured_value": erosion_rate,
            "description": (
                f"墙体段[{segment.name}]风蚀速率{erosion_rate:.3f}mm/年 "
                f"超过阈值{self.erosion_threshold}mm/年，"
                f"超出{((erosion_rate - self.erosion_threshold) / self.erosion_threshold * 100):.1f}%"
            ),
            "timestamp": datetime.now().isoformat(),
            "recommendation": self._get_erosion_recommendation(erosion_rate, alert_level)
        }
        
        mqtt_id = self.publish_alert(alert_data)
        
        alert = Alert(
            segment_id=segment_id,
            alert_type="erosion_rate",
            alert_level=alert_level,
            threshold_value=self.erosion_threshold,
            measured_value=erosion_rate,
            description=alert_data["description"],
            mqtt_message_id=mqtt_id
        )
        db.add(alert)
        await db.flush()
        
        return alert

    async def check_crack_alert(
        self,
        db: AsyncSession,
        segment_id: int,
        crack_data: Dict[str, Any]
    ) -> Optional[Alert]:
        extension_rate = crack_data.get("extension_rate", 0)
        crack_width = crack_data.get("crack_width", 0)
        
        if extension_rate <= self.crack_threshold and crack_width < 2.0:
            return None
        
        segment = await db.get(WallSegment, segment_id)
        if not segment:
            return None
        
        alert_level = "warning"
        if extension_rate > self.crack_threshold * 3 or crack_width > 5.0:
            alert_level = "critical"
        elif extension_rate > self.crack_threshold * 2 or crack_width > 3.0:
            alert_level = "danger"
        
        alert_data = {
            "segment_id": segment_id,
            "segment_name": segment.name,
            "alert_type": "crack_extension",
            "alert_level": alert_level,
            "threshold_value": self.crack_threshold,
            "measured_value": max(extension_rate, crack_width / 10),
            "crack_id": crack_data.get("crack_id"),
            "crack_width": crack_width,
            "extension_rate": extension_rate,
            "location": {
                "x": crack_data.get("location_x"),
                "y": crack_data.get("location_y")
            },
            "description": (
                f"墙体段[{segment.name}]裂缝{crack_data.get('crack_id', '未知')} "
                f"扩展速率{extension_rate:.3f}mm/月，宽度{crack_width:.2f}mm，"
                f"已超过安全阈值"
            ),
            "timestamp": datetime.now().isoformat(),
            "recommendation": self._get_crack_recommendation(extension_rate, crack_width, alert_level)
        }
        
        mqtt_id = self.publish_alert(alert_data)
        
        alert = Alert(
            segment_id=segment_id,
            alert_type="crack_extension",
            alert_level=alert_level,
            threshold_value=self.crack_threshold,
            measured_value=max(extension_rate, crack_width / 10),
            description=alert_data["description"],
            mqtt_message_id=mqtt_id
        )
        db.add(alert)
        await db.flush()
        
        return alert

    async def process_sensor_data(self, sensor_data: Dict[str, Any]) -> Optional[Alert]:
        async with AsyncSessionLocal() as db:
            try:
                from .erosion_model import erosion_simulator
                
                stmt = (
                    select(SensorData)
                    .where(SensorData.segment_id == sensor_data["segment_id"])
                    .order_by(SensorData.time.desc())
                    .limit(24 * 30)
                )
                result = await db.execute(stmt)
                historical_data = result.scalars().all()
                
                if len(historical_data) >= 24:
                    import numpy as np
                    wind_speeds = np.array([d.wind_speed for d in historical_data])
                    wind_directions = np.array([d.wind_direction for d in historical_data])
                    hardness = np.array([d.surface_hardness for d in historical_data])
                    moisture = np.array([d.soil_moisture for d in historical_data])
                    
                    simulation = erosion_simulator.calculate_long_term_erosion_rate(
                        wind_speeds, wind_directions, hardness, moisture
                    )
                    
                    erosion_rate = simulation["erosion_rate_mm_per_year"]
                    return await self.check_erosion_alert(db, sensor_data["segment_id"], erosion_rate)
            except Exception as e:
                logger.error(f"Error processing sensor data for alerts: {e}")
        
        return None

    async def process_crack_data(self, crack_data: Dict[str, Any]) -> Optional[Alert]:
        async with AsyncSessionLocal() as db:
            return await self.check_crack_alert(db, crack_data["segment_id"], crack_data)

    def _get_erosion_recommendation(self, erosion_rate: float, alert_level: str) -> str:
        if alert_level == "critical":
            return "立即启动应急预案：1) 疏散周边人员 2) 搭建临时防护棚 3) 组织专家现场评估 4) 紧急加固处理"
        elif alert_level == "danger":
            return "高风险预警：1) 加强监测频率至每30分钟一次 2) 准备加固材料 3) 制定紧急加固方案 4) 设置警示标志"
        else:
            return "一般预警：1) 关注风蚀发展趋势 2) 评估是否需要提前加固 3) 检查现有防护措施"

    def _get_crack_recommendation(self, extension_rate: float, width: float, alert_level: str) -> str:
        if alert_level == "critical":
            return "裂缝扩展紧急：1) 立即封闭危险区域 2) 安装实时监测设备 3) 结构工程师现场评估 4) 考虑临时支撑"
        elif alert_level == "danger":
            return "裂缝扩展警告：1) 增加监测频率 2) 记录裂缝发展情况 3) 准备注浆加固材料 4) 评估结构稳定性"
        else:
            return "裂缝发展注意：1) 定期观测记录 2) 分析裂缝成因 3) 考虑预防性处理 4) 建立裂缝档案"

    def get_alert_topic(self, segment_id: int, alert_type: str) -> str:
        return f"{settings.MQTT_TOPIC}/{segment_id}/{alert_type}"


mqtt_alert_service = MQTTAlertService()
