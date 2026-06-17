import json
import os
import asyncio
import logging
import redis.asyncio as aioredis
from pathlib import Path
from typing import Any, Dict, Callable, Optional

logger = logging.getLogger("microservices.common")

CONFIG_DIR = Path(__file__).parent.parent / "config"


def load_json_config(filename: str) -> Dict[str, Any]:
    config_path = CONFIG_DIR / filename
    if not config_path.exists():
        logger.error(f"Config file not found: {config_path}")
        return {}
    with open(config_path, "r", encoding="utf-8") as f:
        return json.load(f)


def get_erosion_config() -> Dict[str, Any]:
    return load_json_config("erosion_params.json")


def get_materials_config() -> Dict[str, Any]:
    return load_json_config("reinforcement_materials.json")


class RedisMessageBus:
    CHANNELS = {
        "DTU_DATA_IN": "dtu:data:in",
        "EROSION_REQUEST": "sim:erosion:request",
        "EROSION_RESULT": "sim:erosion:result",
        "TOPSIS_REQUEST": "opt:topsis:request",
        "TOPSIS_RESULT": "opt:topsis:result",
        "ALERT_REQUEST": "alarm:alert:request",
        "ALERT_RESULT": "alarm:alert:result",
    }

    def __init__(self, redis_url: str = None):
        self.redis_url = redis_url or os.getenv("REDIS_URL", "redis://localhost:6379/0")
        self.redis: Optional[aioredis.Redis] = None
        self._pubsub = None
        self._handlers: Dict[str, Callable] = {}
        self._listener_task = None
        self._response_futures: Dict[str, asyncio.Future] = {}

    async def connect(self):
        if self.redis is not None:
            return
        try:
            self.redis = await aioredis.from_url(
                self.redis_url,
                encoding="utf-8",
                decode_responses=True
            )
            await self.redis.ping()
            logger.info("Redis message bus connected")
        except Exception as e:
            logger.warning(f"Redis connection failed, falling back to in-process: {e}")
            self.redis = None

    async def close(self):
        if self._listener_task:
            self._listener_task.cancel()
        if self._pubsub:
            await self._pubsub.unsubscribe()
            await self._pubsub.close()
        if self.redis:
            await self.redis.close()
        logger.info("Redis message bus closed")

    async def publish(self, channel: str, payload: Dict[str, Any], correlation_id: str = None):
        import uuid
        cid = correlation_id or str(uuid.uuid4())
        message = json.dumps({
            "correlation_id": cid,
            "timestamp": __import__("datetime").datetime.now().isoformat(),
            "payload": payload
        }, ensure_ascii=False)
        if self.redis:
            try:
                await self.redis.publish(channel, message)
            except Exception as e:
                logger.error(f"Redis publish failed on {channel}: {e}")
        else:
            self._deliver_local(channel, message)
        return cid

    def _deliver_local(self, channel: str, message: str):
        if channel in self._handlers:
            try:
                msg_data = json.loads(message)
                asyncio.create_task(self._handlers[channel](msg_data["payload"], msg_data["correlation_id"]))
            except Exception as e:
                logger.error(f"Local handler error on {channel}: {e}")

    async def subscribe(self, channel: str, handler: Callable):
        self._handlers[channel] = handler
        if self.redis:
            if self._pubsub is None:
                self._pubsub = self.redis.pubsub()
            await self._pubsub.subscribe(**{channel: self._redis_message_handler})
            if self._listener_task is None:
                self._listener_task = asyncio.create_task(self._pubsub.run())
        logger.info(f"Subscribed to channel: {channel}")

    async def _redis_message_handler(self, message):
        if message["type"] != "message":
            return
        try:
            data = json.loads(message["data"])
            channel = message["channel"]
            cid = data.get("correlation_id")
            payload = data.get("payload", {})
            if cid and cid in self._response_futures and not self._response_futures[cid].done():
                self._response_futures[cid].set_result(payload)
                del self._response_futures[cid]
                return
            if channel in self._handlers:
                await self._handlers[channel](payload, cid)
        except Exception as e:
            logger.error(f"Redis message handler error: {e}")

    async def request_response(self, request_channel: str, response_channel: str,
                                request_payload: Dict[str, Any],
                                timeout: float = 30.0) -> Optional[Dict[str, Any]]:
        import uuid
        cid = str(uuid.uuid4())
        future = asyncio.get_event_loop().create_future()
        self._response_futures[cid] = future

        async def _on_response(payload, resp_cid):
            if resp_cid == cid and cid in self._response_futures:
                if not self._response_futures[cid].done():
                    self._response_futures[cid].set_result(payload)

        await self.subscribe(response_channel, _on_response)
        await self.publish(request_channel, request_payload, correlation_id=cid)

        try:
            result = await asyncio.wait_for(future, timeout=timeout)
            return result
        except asyncio.TimeoutError:
            logger.warning(f"Request-response timeout on {request_channel}")
            return None
        finally:
            if cid in self._response_futures:
                del self._response_futures[cid]


_global_bus: Optional[RedisMessageBus] = None


async def get_message_bus() -> RedisMessageBus:
    global _global_bus
    if _global_bus is None:
        _global_bus = RedisMessageBus()
        await _global_bus.connect()
    return _global_bus
