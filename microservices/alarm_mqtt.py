import json
import os
import uuid
import asyncio
import logging
from datetime import datetime
from typing import Optional, Dict, Any, List
from dataclasses import dataclass, field, asdict

import paho.mqtt.client as mqtt
import numpy as np

from .common import get_erosion_config, get_message_bus, RedisMessageBus

logger = logging.getLogger("alarm_mqtt")


@dataclass
class Alert:
    segment_id: int
    segment_name: str
    alert_type: str
    alert_level: str
    threshold_value: Optional[float] = None
    measured_value: Optional[float] = None
    description: Optional[str] = None
    recommendation: Optional[str] = None
    mqtt_message_id: Optional[str] = None
    crack_id: Optional[str] = None
    crack_width: Optional[float] = None
    extension_rate: Optional[float] = None
    location: Optional[Dict[str, Any]] = None
    extra: Dict[str, Any] = field(default_factory=dict)
    timestamp: str = field(default_factory=lambda: datetime.now().isoformat())

    def to_dict(self) -> Dict[str, Any]:
        data = asdict(self)
        return {k: v for k, v in data.items() if v is not None}


class AlarmMQTTService:
    def __init__(self):
        self.config = get_erosion_config()
        thresholds = self.config.get("erosion_thresholds", {})

        self.EROSION_WARN = thresholds.get("erosion_rate_warning_mm_per_year", 0.5)
        self.EROSION_DANGER_MULT = thresholds.get("erosion_rate_danger_multiplier", 1.5)
        self.EROSION_CRITICAL_MULT = thresholds.get("erosion_rate_critical_multiplier", 2.0)

        self.CRACK_EXTENSION_WARN = thresholds.get("crack_extension_warning_mm_per_month", 0.1)
        self.CRACK_WIDTH_WARN = thresholds.get("crack_width_warning_mm", 2.0)
        self.CRACK_WIDTH_DANGER = thresholds.get("crack_width_danger_mm", 3.0)
        self.CRACK_WIDTH_CRITICAL = thresholds.get("crack_width_critical_mm", 5.0)

        self.mqtt_broker = os.getenv("MQTT_BROKER", "localhost")
        self.mqtt_port = int(os.getenv("MQTT_PORT", "1883"))
        self.mqtt_username = os.getenv("MQTT_USERNAME")
        self.mqtt_password = os.getenv("MQTT_PASSWORD")
        self.mqtt_topic_prefix = os.getenv("MQTT_TOPIC", "wall/alert")

        self.client: Optional[mqtt.Client] = None
        self.connected = False
        self._connect_lock = asyncio.Lock()
        self.bus: Optional[RedisMessageBus] = None

        self._erosion_history: Dict[int, List[Dict[str, Any]]] = {}

    async def ensure_bus(self):
        if self.bus is None:
            self.bus = await get_message_bus()

    def connect(self) -> bool:
        if self.connected and self.client is not None:
            return True
        try:
            self.client = mqtt.Client(
                client_id=f"alarm_mqtt_{uuid.uuid4().hex[:8]}",
                protocol=mqtt.MQTTv5
            )

            if self.mqtt_username and self.mqtt_password:
                self.client.username_pw_set(self.mqtt_username, self.mqtt_password)

            self.client.on_connect = self._on_connect
            self.client.on_disconnect = self._on_disconnect
            self.client.on_publish = self._on_publish

            self.client.connect(
                self.mqtt_broker,
                self.mqtt_port,
                keepalive=60
            )

            self.client.loop_start()
            return True
        except Exception as e:
            logger.error(f"Failed to connect to MQTT broker: {e}")
            self.connected = False
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
            segment_id = alert_data.get("segment_id", "unknown")
            alert_type = alert_data.get("alert_type", "unknown")
            topic = f"{self.mqtt_topic_prefix}/{segment_id}/{alert_type}"
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

    def _get_erosion_level(self, erosion_rate: float) -> Optional[str]:
        if erosion_rate < self.EROSION_WARN:
            return None
        if erosion_rate >= self.EROSION_WARN * self.EROSION_CRITICAL_MULT:
            return "critical"
        elif erosion_rate >= self.EROSION_WARN * self.EROSION_DANGER_MULT:
            return "danger"
        else:
            return "warning"

    def _get_erosion_recommendation(self, erosion_rate: float, alert_level: str) -> str:
        exceed_pct = ((erosion_rate - self.EROSION_WARN) / self.EROSION_WARN * 100)
        if alert_level == "critical":
            return (
                f"立即启动应急预案：风蚀速率{erosion_rate:.3f}mm/年，超出阈值{exceed_pct:.1f}%。"
                "1) 疏散周边人员 2) 搭建临时防护棚 3) 组织专家现场评估 4) 紧急加固处理"
            )
        elif alert_level == "danger":
            return (
                f"高风险预警：风蚀速率{erosion_rate:.3f}mm/年，超出阈值{exceed_pct:.1f}%。"
                "1) 加强监测频率至每30分钟一次 2) 准备加固材料 3) 制定紧急加固方案 4) 设置警示标志"
            )
        else:
            return (
                f"一般预警：风蚀速率{erosion_rate:.3f}mm/年，超出阈值{exceed_pct:.1f}%。"
                "1) 关注风蚀发展趋势 2) 评估是否需要提前加固 3) 检查现有防护措施"
            )

    def check_erosion_alert(
        self,
        segment_id: int,
        segment_name: str,
        erosion_rate: float
    ) -> Optional[Alert]:
        alert_level = self._get_erosion_level(erosion_rate)
        if alert_level is None:
            return None

        description = (
            f"墙体段[{segment_name}]风蚀速率{erosion_rate:.3f}mm/年 "
            f"超过阈值{self.EROSION_WARN}mm/年，"
            f"超出{((erosion_rate - self.EROSION_WARN) / self.EROSION_WARN * 100):.1f}%"
        )

        recommendation = self._get_erosion_recommendation(erosion_rate, alert_level)

        alert = Alert(
            segment_id=segment_id,
            segment_name=segment_name,
            alert_type="erosion_rate",
            alert_level=alert_level,
            threshold_value=self.EROSION_WARN,
            measured_value=erosion_rate,
            description=description,
            recommendation=recommendation
        )

        mqtt_id = self.publish_alert(alert.to_dict())
        alert.mqtt_message_id = mqtt_id

        logger.info(f"Erosion alert generated: seg={segment_id} level={alert_level} rate={erosion_rate:.3f}")
        return alert

    def _get_crack_level(
        self,
        extension_rate: float,
        crack_width: float
    ) -> Optional[str]:
        if extension_rate < self.CRACK_EXTENSION_WARN and crack_width < self.CRACK_WIDTH_WARN:
            return None

        level_ext = None
        if extension_rate >= self.CRACK_EXTENSION_WARN * 3:
            level_ext = "critical"
        elif extension_rate >= self.CRACK_EXTENSION_WARN * 2:
            level_ext = "danger"
        elif extension_rate >= self.CRACK_EXTENSION_WARN:
            level_ext = "warning"

        level_width = None
        if crack_width >= self.CRACK_WIDTH_CRITICAL:
            level_width = "critical"
        elif crack_width >= self.CRACK_WIDTH_DANGER:
            level_width = "danger"
        elif crack_width >= self.CRACK_WIDTH_WARN:
            level_width = "warning"

        priority = {"warning": 1, "danger": 2, "critical": 3}
        levels = [l for l in [level_ext, level_width] if l is not None]
        if not levels:
            return None
        return max(levels, key=lambda l: priority[l])

    def _get_crack_recommendation(
        self,
        extension_rate: float,
        width: float,
        alert_level: str
    ) -> str:
        if alert_level == "critical":
            return (
                f"裂缝扩展紧急：扩展速率{extension_rate:.3f}mm/月，宽度{width:.2f}mm。"
                "1) 立即封闭危险区域 2) 安装实时监测设备 3) 结构工程师现场评估 4) 考虑临时支撑"
            )
        elif alert_level == "danger":
            return (
                f"裂缝扩展警告：扩展速率{extension_rate:.3f}mm/月，宽度{width:.2f}mm。"
                "1) 增加监测频率 2) 记录裂缝发展情况 3) 准备注浆加固材料 4) 评估结构稳定性"
            )
        else:
            return (
                f"裂缝发展注意：扩展速率{extension_rate:.3f}mm/月，宽度{width:.2f}mm。"
                "1) 定期观测记录 2) 分析裂缝成因 3) 考虑预防性处理 4) 建立裂缝档案"
            )

    def check_crack_alert(
        self,
        segment_id: int,
        segment_name: str,
        crack_data: Dict[str, Any]
    ) -> Optional[Alert]:
        extension_rate = crack_data.get("extension_rate", 0) or 0
        crack_width = crack_data.get("crack_width", 0) or 0

        alert_level = self._get_crack_level(extension_rate, crack_width)
        if alert_level is None:
            return None

        crack_id = crack_data.get("crack_id", "未知")
        description = (
            f"墙体段[{segment_name}]裂缝{crack_id} "
            f"扩展速率{extension_rate:.3f}mm/月，宽度{crack_width:.2f}mm，"
            f"已超过安全阈值"
        )

        recommendation = self._get_crack_recommendation(extension_rate, crack_width, alert_level)

        location = None
        loc_x = crack_data.get("location_x")
        loc_y = crack_data.get("location_y")
        if loc_x is not None or loc_y is not None:
            location = {"x": loc_x, "y": loc_y}

        alert = Alert(
            segment_id=segment_id,
            segment_name=segment_name,
            alert_type="crack_extension",
            alert_level=alert_level,
            threshold_value=self.CRACK_EXTENSION_WARN,
            measured_value=max(extension_rate, crack_width / 10),
            description=description,
            recommendation=recommendation,
            crack_id=crack_id if crack_id != "未知" else None,
            crack_width=crack_width,
            extension_rate=extension_rate,
            location=location
        )

        mqtt_id = self.publish_alert(alert.to_dict())
        alert.mqtt_message_id = mqtt_id

        logger.info(f"Crack alert generated: seg={segment_id} level={alert_level} ext={extension_rate:.3f} width={crack_width:.2f}")
        return alert

    def _compute_erosion_rate_from_history(
        self,
        history: List[Dict[str, Any]]
    ) -> float:
        if len(history) < 2:
            return 0.0

        sorted_history = sorted(history, key=lambda d: d.get("time", ""))
        first = sorted_history[0]
        last = sorted_history[-1]

        try:
            t_first = datetime.fromisoformat(first["time"].replace("Z", "+00:00"))
            t_last = datetime.fromisoformat(last["time"].replace("Z", "+00:00"))
        except (ValueError, KeyError):
            return 0.0

        delta_hours = (t_last - t_first).total_seconds() / 3600.0
        if delta_hours < 1:
            return 0.0

        depth_first = float(first.get("wind_erosion_depth", 0))
        depth_last = float(last.get("wind_erosion_depth", 0))
        delta_depth_mm = max(0.0, depth_last - depth_first)

        erosion_rate = (delta_depth_mm / delta_hours) * 365 * 24
        return erosion_rate

    def _update_history(self, segment_id: int, data: Dict[str, Any]):
        if segment_id not in self._erosion_history:
            self._erosion_history[segment_id] = []
        self._erosion_history[segment_id].append(dict(data))

        max_points = 24 * 30
        hist = self._erosion_history[segment_id]
        if len(hist) > max_points:
            self._erosion_history[segment_id] = hist[-max_points:]

    def process_sensor_data_for_alert(
        self,
        payload: Dict[str, Any]
    ) -> Dict[str, Any]:
        segment_id = payload.get("segment_id")
        if segment_id is None:
            return {"ok": False, "error": "missing segment_id", "alert": None}

        if isinstance(payload, dict) and payload.get("type") == "batch" and "items" in payload:
            items = payload["items"]
            for item in items:
                sid = item.get("segment_id")
                if sid is not None:
                    self._update_history(sid, item)
        else:
            self._update_history(segment_id, payload)

        history = self._erosion_history.get(segment_id, [])
        if len(history) < 24:
            return {
                "ok": True,
                "alert": None,
                "message": f"insufficient history: {len(history)}/24 points",
                "segment_id": segment_id
            }

        erosion_rate = self._compute_erosion_rate_from_history(history)

        segment_name = payload.get("segment_name") or f"Segment-{segment_id}"
        alert = self.check_erosion_alert(segment_id, segment_name, erosion_rate)

        return {
            "ok": True,
            "alert": alert.to_dict() if alert else None,
            "erosion_rate": erosion_rate,
            "data_points": len(history),
            "segment_id": segment_id,
            "segment_name": segment_name
        }

    async def handle_alert_request(
        self,
        payload: Dict[str, Any],
        cid: str
    ):
        await self.ensure_bus()

        mode = payload.get("mode")
        result: Dict[str, Any] = {"ok": True, "mode": mode, "correlation_id": cid}

        try:
            if mode == "erosion_check":
                segment_id = payload.get("segment_id")
                segment_name = payload.get("segment_name") or f"Segment-{segment_id}"
                erosion_rate = float(payload.get("erosion_rate", 0))
                alert = self.check_erosion_alert(segment_id, segment_name, erosion_rate)
                result["alert"] = alert.to_dict() if alert else None
                result["erosion_rate"] = erosion_rate

            elif mode == "crack_check":
                segment_id = payload.get("segment_id")
                segment_name = payload.get("segment_name") or f"Segment-{segment_id}"
                crack_data = payload.get("crack_data", payload)
                alert = self.check_crack_alert(segment_id, segment_name, crack_data)
                result["alert"] = alert.to_dict() if alert else None

            elif mode == "process_data":
                sensor_payload = payload.get("data", payload)
                process_result = self.process_sensor_data_for_alert(sensor_payload)
                result.update(process_result)

            else:
                result["ok"] = False
                result["error"] = f"unknown mode: {mode}"

        except Exception as e:
            logger.error(f"handle_alert_request error: {e}", exc_info=True)
            result["ok"] = False
            result["error"] = str(e)

        if self.bus:
            await self.bus.publish(
                RedisMessageBus.CHANNELS["ALERT_RESULT"],
                result,
                correlation_id=cid
            )

        return result

    async def _handle_dtu_data(
        self,
        payload: Dict[str, Any],
        cid: str
    ):
        try:
            result = self.process_sensor_data_for_alert(payload)
            if result.get("alert") and self.bus:
                await self.bus.publish(
                    RedisMessageBus.CHANNELS["ALERT_RESULT"],
                    result,
                    correlation_id=cid
                )
        except Exception as e:
            logger.error(f"_handle_dtu_data error: {e}", exc_info=True)


_alarm_service: Optional[AlarmMQTTService] = None


def get_alarm_service() -> AlarmMQTTService:
    global _alarm_service
    if _alarm_service is None:
        _alarm_service = AlarmMQTTService()
    return _alarm_service


async def start_alarm_mqtt_service():
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s - %(name)s - %(levelname)s - %(message)s"
    )
    logger.info("Starting AlarmMQTTService microservice...")

    bus = await get_message_bus()
    service = get_alarm_service()
    service.bus = bus

    logger.info(f"Subscribing to ALERT_REQUEST channel: {RedisMessageBus.CHANNELS['ALERT_REQUEST']}")
    await bus.subscribe(
        RedisMessageBus.CHANNELS["ALERT_REQUEST"],
        service.handle_alert_request
    )

    logger.info(f"Subscribing to DTU_DATA_IN channel: {RedisMessageBus.CHANNELS['DTU_DATA_IN']}")
    await bus.subscribe(
        RedisMessageBus.CHANNELS["DTU_DATA_IN"],
        service._handle_dtu_data
    )

    mqtt_ok = service.connect()
    logger.info(f"MQTT broker connection attempt: {'success' if mqtt_ok else 'failed (will retry lazily)'}")

    logger.info("AlarmMQTTService microservice started successfully")
    logger.info(f"Thresholds: EROSION_WARN={service.EROSION_WARN}, "
                f"EROSION_DANGER_MULT={service.EROSION_DANGER_MULT}, "
                f"EROSION_CRITICAL_MULT={service.EROSION_CRITICAL_MULT}")
    logger.info(f"Thresholds: CRACK_EXTENSION_WARN={service.CRACK_EXTENSION_WARN}, "
                f"CRACK_WIDTH_WARN/DANGER/CRITICAL={service.CRACK_WIDTH_WARN}/{service.CRACK_WIDTH_DANGER}/{service.CRACK_WIDTH_CRITICAL}")

    try:
        while True:
            await asyncio.sleep(60)
    except asyncio.CancelledError:
        logger.info("AlarmMQTTService shutting down...")
        service.disconnect()
        await bus.close()
        logger.info("AlarmMQTTService stopped")


if __name__ == "__main__":
    asyncio.run(start_alarm_mqtt_service())
