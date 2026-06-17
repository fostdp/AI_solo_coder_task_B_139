import sys
import os
import logging
from pathlib import Path
from typing import Any, Dict, Optional

_project_root = Path(__file__).parent.parent.resolve()
if str(_project_root) not in sys.path:
    sys.path.insert(0, str(_project_root))

import numpy as np

try:
    from microservices import (
        dtu_receiver,
        wind_erosion_simulator,
        reinforcement_optimizer,
        alarm_mqtt,
        common,
    )
    from microservices.common import RedisMessageBus, get_message_bus
except Exception as _import_e:
    logging.getLogger("adapters").error(f"Failed to import microservices: {_import_e}")
    dtu_receiver = None
    wind_erosion_simulator = None
    reinforcement_optimizer = None
    alarm_mqtt = None
    common = None
    RedisMessageBus = None
    get_message_bus = None

logger = logging.getLogger("adapters")


class MicroserviceAdapter:
    def __init__(self):
        self.local_only = False
        self.bus: Optional[RedisMessageBus] = None
        self.dtu_receiver = None
        self.erosion_sim = None
        self.optimizer = None
        self.alarm = None
        self._services_started = False

        try:
            if dtu_receiver is not None:
                self.dtu_receiver = dtu_receiver.get_dtu_receiver()
        except Exception as e:
            logger.error(f"Failed to init dtu_receiver: {e}")

        try:
            if wind_erosion_simulator is not None:
                self.erosion_sim = wind_erosion_simulator.get_erosion_simulator()
        except Exception as e:
            logger.error(f"Failed to init erosion_sim: {e}")

        try:
            if reinforcement_optimizer is not None:
                self.optimizer = reinforcement_optimizer.get_optimizer()
        except Exception as e:
            logger.error(f"Failed to init optimizer: {e}")

        try:
            if alarm_mqtt is not None:
                self.alarm = alarm_mqtt.get_alarm_service()
        except Exception as e:
            logger.error(f"Failed to init alarm: {e}")

    async def _try_connect_bus(self):
        if self.bus is not None or self.local_only:
            return
        try:
            if get_message_bus is not None:
                self.bus = await get_message_bus()
                if self.bus is not None and self.bus.redis is None:
                    logger.warning("Redis unavailable, marking as local_only=True")
                    self.local_only = True
                    self.bus = None
            else:
                self.local_only = True
        except Exception as e:
            logger.warning(f"Failed to connect message bus, falling back to in-process: {e}")
            self.local_only = True
            self.bus = None

    async def ensure_services(self):
        await self._try_connect_bus()

        if self._services_started:
            return
        self._services_started = True

        try:
            if self.bus is not None and self.erosion_sim is not None:
                self.erosion_sim.bus = self.bus
                await self.bus.subscribe(
                    RedisMessageBus.CHANNELS["EROSION_REQUEST"],
                    self.erosion_sim.handle_erosion_request,
                )
                logger.info("Erosion simulator subscribed to request channel")
        except Exception as e:
            logger.error(f"Failed to subscribe erosion sim: {e}")

        try:
            if self.bus is not None and self.optimizer is not None:
                self.optimizer.bus = self.bus
                await self.bus.subscribe(
                    RedisMessageBus.CHANNELS["TOPSIS_REQUEST"],
                    self.optimizer.handle_topsis_request,
                )
                logger.info("Optimizer subscribed to request channel")
        except Exception as e:
            logger.error(f"Failed to subscribe optimizer: {e}")

        try:
            if self.bus is not None and self.alarm is not None:
                self.alarm.bus = self.bus
                await self.bus.subscribe(
                    RedisMessageBus.CHANNELS["ALERT_REQUEST"],
                    self.alarm.handle_alert_request,
                )
                await self.bus.subscribe(
                    RedisMessageBus.CHANNELS["DTU_DATA_IN"],
                    self.alarm._handle_dtu_data,
                )
                logger.info("Alarm service subscribed to request channels")
        except Exception as e:
            logger.error(f"Failed to subscribe alarm service: {e}")

    async def send_dtu_data(self, data: Dict[str, Any]) -> Dict[str, Any]:
        try:
            if self.bus is not None:
                if self.dtu_receiver is not None:
                    return await self.dtu_receiver.receive(data, publish=True)
                else:
                    return {"ok": False, "error": "dtu_receiver unavailable", "data": data, "published_cid": None}
            else:
                if self.dtu_receiver is not None:
                    result = await self.dtu_receiver.receive(data, publish=False)
                    if self.alarm is not None and result.get("ok"):
                        try:
                            processed = self.alarm.process_sensor_data_for_alert(result.get("data", data))
                            result["alert_processed"] = processed
                        except Exception as ae:
                            logger.warning(f"Manual alarm processing failed: {ae}")
                            result["alert_processed"] = {"ok": False, "error": str(ae)}
                    return result
                else:
                    return {"ok": False, "error": "dtu_receiver unavailable", "data": data, "published_cid": None}
        except Exception as e:
            logger.error(f"send_dtu_data exception: {e}")
            return {"ok": False, "error": str(e), "data": data, "published_cid": None}

    async def call_erosion_sim(self, mode: str, **kwargs) -> Dict[str, Any]:
        try:
            if self.bus is not None and RedisMessageBus is not None:
                payload = {"mode": mode, **kwargs}
                result = await self.bus.request_response(
                    RedisMessageBus.CHANNELS["EROSION_REQUEST"],
                    RedisMessageBus.CHANNELS["EROSION_RESULT"],
                    payload,
                    timeout=30.0,
                )
                if result is not None:
                    return result
                logger.warning("request_response returned None, falling back to in-process")

            if self.erosion_sim is None:
                return {"ok": False, "error": "erosion_sim unavailable", "mode": mode}

            if mode == "long_term":
                try:
                    ws = np.array(kwargs.get("wind_speeds", []))
                    wd = np.array(kwargs.get("wind_directions", []))
                    hh = np.array(kwargs.get("hardness", []))
                    mm = np.array(kwargs.get("moisture", []))
                    sim_result = self.erosion_sim.calculate_long_term_erosion_rate(ws, wd, hh, mm)
                    return {"ok": True, "result": sim_result, "mode": mode, "local": True}
                except Exception as ie:
                    return {"ok": False, "error": f"long_term error: {ie}", "mode": mode}

            elif mode == "two_phase_flow_des":
                try:
                    sim_result = self.erosion_sim.simulate_two_phase_flow_with_des(
                        kwargs.get("wind_speed", 5.0),
                        kwargs.get("wind_direction", 180.0),
                        kwargs.get("surface_hardness", 2.5),
                        kwargs.get("soil_moisture", 5.0),
                        kwargs.get("wall_geometry"),
                        kwargs.get("duration_hours", 1.0),
                        kwargs.get("grid_resolution", 20),
                    )
                    return {"ok": True, "result": sim_result, "mode": mode, "local": True}
                except Exception as ie:
                    return {"ok": False, "error": f"two_phase_flow_des error: {ie}", "mode": mode}

            elif mode == "wind_field":
                try:
                    field_data = self.erosion_sim.generate_wind_field(
                        kwargs.get("wind_speed", 5.0),
                        kwargs.get("wind_direction", 180.0),
                        tuple(kwargs.get("grid_size", (10, 5, 5))),
                        tuple(kwargs.get("bounds", (0, 10, 0, 5, 0, 3))),
                    )
                    return {"ok": True, "result": {"field_data": field_data}, "mode": mode, "local": True}
                except Exception as ie:
                    return {"ok": False, "error": f"wind_field error: {ie}", "mode": mode}

            else:
                return {"ok": False, "error": f"unknown mode: {mode}", "mode": mode}

        except Exception as e:
            logger.error(f"call_erosion_sim exception: {e}")
            return {"ok": False, "error": str(e), "mode": mode}

    async def call_optimizer(self, mode: str, **kwargs) -> Dict[str, Any]:
        try:
            if self.bus is not None and RedisMessageBus is not None:
                payload = {"mode": mode, **kwargs}
                result = await self.bus.request_response(
                    RedisMessageBus.CHANNELS["TOPSIS_REQUEST"],
                    RedisMessageBus.CHANNELS["TOPSIS_RESULT"],
                    payload,
                    timeout=30.0,
                )
                if result is not None:
                    return result
                logger.warning("request_response returned None, falling back to in-process")

            if self.optimizer is None:
                return {"ok": False, "error": "optimizer unavailable", "mode": mode}

            if mode == "generate":
                try:
                    segment_id = kwargs.get("segment_id")
                    area_sqm = kwargs.get("area_sqm", 10.0)
                    hardness = kwargs.get("hardness", 2.5)
                    moisture = kwargs.get("moisture", 5.0)
                    severity = kwargs.get("severity", "medium")
                    plans = self.optimizer.generate_reinforcement_plans(
                        segment_id, area_sqm, hardness, moisture, severity
                    )
                    auto_evaluate = kwargs.get("auto_evaluate", True)
                    if auto_evaluate and plans:
                        criteria_defaults = getattr(self.optimizer, "criteria_defaults", {})
                        criteria = list(criteria_defaults.get("weights", {}).keys())
                        weights = criteria_defaults.get("weights", {})
                        benefit = criteria_defaults.get("benefit_criteria", [])
                        cost = criteria_defaults.get("cost_criteria", [])
                        rankings = self.optimizer.evaluate(plans, criteria, weights, benefit, cost)
                        return {"ok": True, "result": {"plans": plans, "rankings": rankings}, "mode": mode, "local": True}
                    return {"ok": True, "result": {"plans": plans}, "mode": mode, "local": True}
                except Exception as ie:
                    return {"ok": False, "error": f"generate error: {ie}", "mode": mode}

            elif mode == "evaluate":
                try:
                    alternatives = kwargs.get("alternatives", [])
                    criteria_defaults = getattr(self.optimizer, "criteria_defaults", {})
                    criteria = kwargs.get("criteria") or list(criteria_defaults.get("weights", {}).keys())
                    criteria = list(criteria)
                    weights = kwargs.get("weights") or criteria_defaults.get("weights", {})
                    benefit_criteria = kwargs.get("benefit_criteria") or criteria_defaults.get("benefit_criteria", [])
                    cost_criteria = kwargs.get("cost_criteria") or criteria_defaults.get("cost_criteria", [])
                    rankings = self.optimizer.evaluate(
                        alternatives, criteria, weights, benefit_criteria, cost_criteria
                    )
                    return {"ok": True, "result": {"rankings": rankings}, "mode": mode, "local": True}
                except Exception as ie:
                    return {"ok": False, "error": f"evaluate error: {ie}", "mode": mode}

            elif mode == "penetration":
                try:
                    material_code = kwargs.get("material_code", "TEOS-01")
                    material_ratio = kwargs.get("material_ratio", "100%")
                    surface_hardness = kwargs.get("surface_hardness", 2.5)
                    soil_moisture = kwargs.get("soil_moisture", 5.0)
                    application_pressure = kwargs.get("application_pressure", 0.5)
                    depth = self.optimizer.calculate_penetration_depth(
                        material_code, material_ratio, surface_hardness, soil_moisture, application_pressure
                    )
                    durability = self.optimizer.calculate_durability_with_confidence(material_code, depth)
                    return {
                        "ok": True,
                        "result": {"penetration_depth": depth, "durability": durability},
                        "mode": mode,
                        "local": True,
                    }
                except Exception as ie:
                    return {"ok": False, "error": f"penetration error: {ie}", "mode": mode}

            elif mode == "durability":
                try:
                    material_code = kwargs.get("material_code", "TEOS-01")
                    penetration_depth = kwargs.get("penetration_depth", 10.0)
                    durability = self.optimizer.calculate_durability_with_confidence(
                        material_code, penetration_depth
                    )
                    return {"ok": True, "result": durability, "mode": mode, "local": True}
                except Exception as ie:
                    return {"ok": False, "error": f"durability error: {ie}", "mode": mode}

            elif mode == "aging_simulation":
                try:
                    material_code = kwargs.get("material_code", "TEOS-01")
                    test_T = kwargs.get("test_temperature")
                    test_RH = kwargs.get("test_humidity")
                    test_days = kwargs.get("test_days")
                    sim_data = self.optimizer.run_accelerated_aging_simulation(
                        material_code, test_T, test_RH, test_days
                    )
                    return {"ok": True, "result": {"simulation_data": sim_data}, "mode": mode, "local": True}
                except Exception as ie:
                    return {"ok": False, "error": f"aging_simulation error: {ie}", "mode": mode}

            else:
                return {"ok": False, "error": f"unknown mode: {mode}", "mode": mode}

        except Exception as e:
            logger.error(f"call_optimizer exception: {e}")
            return {"ok": False, "error": str(e), "mode": mode}

    async def call_alarm(self, mode: str, **kwargs) -> Dict[str, Any]:
        try:
            if self.bus is not None and RedisMessageBus is not None:
                payload = {"mode": mode, **kwargs}
                result = await self.bus.request_response(
                    RedisMessageBus.CHANNELS["ALERT_REQUEST"],
                    RedisMessageBus.CHANNELS["ALERT_RESULT"],
                    payload,
                    timeout=30.0,
                )
                if result is not None:
                    return result
                logger.warning("request_response returned None, falling back to in-process")

            if self.alarm is None:
                return {"ok": False, "error": "alarm service unavailable", "mode": mode}

            if mode == "erosion_check" or mode == "check_erosion_alert":
                try:
                    segment_id = kwargs.get("segment_id")
                    segment_name = kwargs.get("segment_name") or f"Segment-{segment_id}"
                    erosion_rate = float(kwargs.get("erosion_rate", 0))
                    alert = self.alarm.check_erosion_alert(segment_id, segment_name, erosion_rate)
                    alert_dict = None
                    if alert is not None:
                        alert_dict = alert.to_dict()
                    return {
                        "ok": True,
                        "mode": mode,
                        "alert": alert_dict,
                        "erosion_rate": erosion_rate,
                        "local": True,
                    }
                except Exception as ie:
                    return {"ok": False, "error": f"erosion_check error: {ie}", "mode": mode}

            elif mode == "crack_check" or mode == "check_crack_alert":
                try:
                    segment_id = kwargs.get("segment_id")
                    segment_name = kwargs.get("segment_name") or f"Segment-{segment_id}"
                    crack_data = kwargs.get("crack_data", kwargs)
                    alert = self.alarm.check_crack_alert(segment_id, segment_name, crack_data)
                    alert_dict = None
                    if alert is not None:
                        alert_dict = alert.to_dict()
                    return {"ok": True, "mode": mode, "alert": alert_dict, "local": True}
                except Exception as ie:
                    return {"ok": False, "error": f"crack_check error: {ie}", "mode": mode}

            elif mode == "process_data":
                try:
                    sensor_payload = kwargs.get("data", kwargs)
                    process_result = self.alarm.process_sensor_data_for_alert(sensor_payload)
                    result = {"ok": True, "mode": mode, "local": True}
                    result.update(process_result)
                    return result
                except Exception as ie:
                    return {"ok": False, "error": f"process_data error: {ie}", "mode": mode}

            else:
                return {"ok": False, "error": f"unknown mode: {mode}", "mode": mode}

        except Exception as e:
            logger.error(f"call_alarm exception: {e}")
            return {"ok": False, "error": str(e), "mode": mode}


_adapter: Optional[MicroserviceAdapter] = None


def get_adapter() -> MicroserviceAdapter:
    global _adapter
    if _adapter is None:
        _adapter = MicroserviceAdapter()
    return _adapter
