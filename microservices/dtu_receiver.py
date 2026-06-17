import asyncio
import logging
import re
from datetime import datetime
from typing import Any, Dict, List, Optional, Tuple
from .common import get_erosion_config, get_message_bus, RedisMessageBus

logger = logging.getLogger("dtu_receiver")

SENSOR_ID_PATTERN = re.compile(r"^[A-Za-z0-9_-]{3,50}$")


class DTUDataReceiver:
    """
    传感器数据接收与校验模块。
    职责：
      1. 接收来自4G DTU的原始传感器数据包（单条/批量）
      2. 数据完整性和范围校验
      3. 异常值/跳跃值过滤
      4. 发布到Redis总线，供其他微服务订阅
    向后兼容：作为单例被FastAPI路由直接调用
    """

    def __init__(self, bus: RedisMessageBus = None):
        self.config = get_erosion_config()
        self.bus = bus
        self._last_values: Dict[int, Dict[str, float]] = {}
        self._jump_thresholds = {
            "wind_erosion_depth": 0.5,
            "surface_hardness": 1.5,
            "soil_moisture": 10.0,
            "wind_speed": 20.0,
        }
        self.valid_ranges = {
            "wind_erosion_depth": (0.0, 1000.0),
            "soil_moisture": (0.0, 50.0),
            "surface_hardness": (0.1, 20.0),
            "wind_speed": (0.0, 60.0),
            "wind_direction": (0.0, 360.0),
            "temperature": (-40.0, 80.0),
            "humidity": (0.0, 100.0),
        }

    async def ensure_bus(self):
        if self.bus is None:
            self.bus = await get_message_bus()

    def validate_single(self, data: Dict[str, Any]) -> Tuple[bool, List[str]]:
        errors: List[str] = []

        required_fields = [
            "segment_id", "sensor_id", "time",
            "wind_erosion_depth", "soil_moisture",
            "surface_hardness", "wind_speed", "wind_direction"
        ]
        for f in required_fields:
            if f not in data or data[f] is None:
                errors.append(f"missing field: {f}")
        if errors:
            return False, errors

        if not isinstance(data["segment_id"], int) or data["segment_id"] <= 0:
            errors.append("segment_id must be positive int")

        if not SENSOR_ID_PATTERN.match(str(data["sensor_id"])):
            errors.append("invalid sensor_id format")

        for field, (lo, hi) in self.valid_ranges.items():
            if field in data and isinstance(data[field], (int, float)):
                v = float(data[field])
                if not (lo <= v <= hi):
                    errors.append(f"{field}={v} out of range [{lo},{hi}]")

        segment_id = data.get("segment_id")
        if segment_id in self._last_values and not errors:
            last = self._last_values[segment_id]
            for field, thr in self._jump_thresholds.items():
                if field in data and field in last:
                    jump = abs(float(data[field]) - float(last[field]))
                    if jump > thr:
                        logger.warning(
                            f"Jump detected seg={segment_id} {field}: "
                            f"{last[field]} -> {data[field]} (>{thr})"
                        )

        return (len(errors) == 0), errors

    def filter_and_clamp(self, data: Dict[str, Any]) -> Dict[str, Any]:
        cleaned = dict(data)
        for field, (lo, hi) in self.valid_ranges.items():
            if field in cleaned and isinstance(cleaned[field], (int, float)):
                v = float(cleaned[field])
                if v < lo:
                    cleaned[field] = lo
                    logger.debug(f"Clamped {field}: {v} -> {lo}")
                elif v > hi:
                    cleaned[field] = hi
                    logger.debug(f"Clamped {field}: {v} -> {hi}")
        if "time" not in cleaned or not cleaned["time"]:
            cleaned["time"] = datetime.now().isoformat()
        return cleaned

    def update_memory(self, data: Dict[str, Any]):
        sid = data.get("segment_id")
        if not sid:
            return
        snapshot = {
            k: data[k] for k in self._jump_thresholds.keys()
            if k in data and isinstance(data[k], (int, float))
        }
        self._last_values[sid] = snapshot

    async def receive(self, raw_data: Dict[str, Any], publish: bool = True) -> Dict[str, Any]:
        """处理单条传感器数据，返回 {ok, errors, data, published_cid}"""
        await self.ensure_bus()
        cleaned = self.filter_and_clamp(raw_data)
        ok, errors = self.validate_single(cleaned)
        result = {"ok": ok, "errors": errors, "data": cleaned, "published_cid": None}
        if not ok:
            logger.error(f"Validation failed: {errors} | data={cleaned}")
            return result
        self.update_memory(cleaned)
        if publish and self.bus:
            cid = await self.bus.publish(
                RedisMessageBus.CHANNELS["DTU_DATA_IN"],
                cleaned
            )
            result["published_cid"] = cid
        return result

    async def receive_batch(self, raw_list: List[Dict[str, Any]], publish: bool = True) -> Dict[str, Any]:
        await self.ensure_bus()
        passed = []
        failed = []
        for i, raw in enumerate(raw_list):
            res = await self.receive(raw, publish=False)
            if res["ok"]:
                passed.append(res["data"])
            else:
                failed.append({"index": i, "errors": res["errors"], "data": raw})
        cid = None
        if publish and passed and self.bus:
            cid = await self.bus.publish(
                RedisMessageBus.CHANNELS["DTU_DATA_IN"],
                {"type": "batch", "count": len(passed), "items": passed}
            )
        return {
            "total": len(raw_list),
            "passed": len(passed),
            "failed": len(failed),
            "passed_items": passed,
            "failed_items": failed,
            "published_cid": cid
        }


_receiver: Optional[DTUDataReceiver] = None


def get_dtu_receiver() -> DTUDataReceiver:
    global _receiver
    if _receiver is None:
        _receiver = DTUDataReceiver()
    return _receiver


async def start_dtu_receiver_service():
    """独立微服务启动入口：订阅外部DTU HTTP推流"""
    logging.basicConfig(level=logging.INFO)
    bus = await get_message_bus()
    receiver = DTUDataReceiver(bus=bus)
    logger.info("DTU Receiver microservice started")
    logger.info(f"Channels: {RedisMessageBus.CHANNELS['DTU_DATA_IN']}")
    while True:
        await asyncio.sleep(60)


if __name__ == "__main__":
    asyncio.run(start_dtu_receiver_service())
