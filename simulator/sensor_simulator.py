#!/usr/bin/env python3
"""
夯土墙传感器模拟器 - 模拟4G DTU数据上报
支持：可配置风速范围/偏差/季节/昼夜因子、可配置含水量基础值/偏差/方差

环境变量（Docker部署时使用）：
    SIM_API_URL           默认 http://localhost:8000
    SIM_INTERVAL          默认 3600 秒
    SIM_SEGMENTS          默认 8
    SIM_GENERATE_HISTORICAL  true/false 默认true
    SIM_HISTORICAL_DAYS   默认 30
    SIM_WIND_SPEED_MIN    默认 2.0 (m/s)
    SIM_WIND_SPEED_MAX    默认 12.0 (m/s)
    SIM_WIND_SPEED_BIAS   默认 0.0 (全局风速偏移，正值加大，正值减弱)
    SIM_WIND_GUST_FREQ    默认 0.2 (阵风频率)
    SIM_SEASONAL_FACTOR   默认 1.0 (季节系数，1.3为春季大风)
    SIM_DIURNAL_ENABLE    默认 true (启用昼夜差异)
    SIM_MOISTURE_BASE     默认 5.0 (%)
    SIM_MOISTURE_BIAS     默认 0.0 (%)
    SIM_MOISTURE_VAR_MIN  默认 0.5 (相对变异最小系数)
    SIM_MOISTURE_VAR_MAX  默认 1.5 (相对变异最大系数)
    SIM_DOMINANT_WIND_DIR 默认 225 (主导风向度数，225=西南风)
"""

import asyncio
import httpx
import json
import os
import random
import logging
from datetime import datetime, timedelta
from typing import Dict, List, Any, Optional
import numpy as np

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s"
)
logger = logging.getLogger("SensorSimulator")


def _env_bool(key: str, default: bool = True) -> bool:
    v = os.environ.get(key)
    if v is None:
        return default
    return v.lower() in ("1", "true", "yes", "on", "y")


def _env_float(key: str, default: float) -> float:
    v = os.environ.get(key)
    if v is None or v == "":
        return default
    try:
        return float(v)
    except ValueError:
        return default


def _env_int(key: str, default: int) -> int:
    v = os.environ.get(key)
    if v is None or v == "":
        return default
    try:
        return int(v)
    except ValueError:
        return default


class SimConfig:
    """模拟器全局配置（环境变量优先，命令行其次）"""

    def __init__(
        self,
        api_url: Optional[str] = None,
        interval: Optional[int] = None,
        segments: Optional[int] = None,
        generate_historical: Optional[bool] = None,
        historical_days: Optional[int] = None,
    ):
        self.api_url = api_url or os.environ.get("SIM_API_URL", "http://localhost:8000")
        self.interval = interval if interval is not None else _env_int("SIM_INTERVAL", 3600)
        self.num_segments = segments if segments is not None else _env_int("SIM_SEGMENTS", 8)
        self.generate_historical = (
            generate_historical
            if generate_historical is not None
            else _env_bool("SIM_GENERATE_HISTORICAL", True)
        )
        self.historical_days = (
            historical_days
            if historical_days is not None
            else _env_int("SIM_HISTORICAL_DAYS", 30)
        )

        # ====== 风速参数 ======
        self.wind_speed_min = _env_float("SIM_WIND_SPEED_MIN", 2.0)
        self.wind_speed_max = _env_float("SIM_WIND_SPEED_MAX", 12.0)
        self.wind_speed_bias = _env_float("SIM_WIND_SPEED_BIAS", 0.0)
        self.wind_gust_freq = _env_float("SIM_WIND_GUST_FREQ", 0.2)
        self.seasonal_factor = _env_float("SIM_SEASONAL_FACTOR", 1.0)  # 1.3=春季大风
        self.diurnal_enable = _env_bool("SIM_DIURNAL_ENABLE", True)
        self.dominant_wind_dir = _env_float("SIM_DOMINANT_WIND_DIR", 225.0)  # 西南风

        # ====== 含水量参数 ======
        self.moisture_base = _env_float("SIM_MOISTURE_BASE", 5.0)  # %
        self.moisture_bias = _env_float("SIM_MOISTURE_BIAS", 0.0)   # %
        self.moisture_var_min = _env_float("SIM_MOISTURE_VAR_MIN", 0.5)
        self.moisture_var_max = _env_float("SIM_MOISTURE_VAR_MAX", 1.5)

    def summary(self) -> str:
        lines = [
            "========= 夯土墙传感器模拟器配置 =========",
            f"  API地址:           {self.api_url}",
            f"  上报间隔:          {self.interval}秒",
            f"  墙段数量:          {self.num_segments}",
            f"  生成历史:          {'是(' + str(self.historical_days) + '天)' if self.generate_historical else '否'}",
            "  --- 风速配置 ---",
            f"    范围:            {self.wind_speed_min:.1f} ~ {self.wind_speed_max:.1f} m/s",
            f"    全局偏移:        {self.wind_speed_bias:+.1f} m/s",
            f"    阵风频率:        {self.wind_gust_freq:.0%}",
            f"    季节系数:        {self.seasonal_factor:.2f}",
            f"    昼夜差异:        {'启用' if self.diurnal_enable else '禁用'}",
            f"    主导风向:        {self.dominant_wind_dir:.0f}°",
            "  --- 含水量配置 ---",
            f"    基础值:          {self.moisture_base:.1f}%",
            f"    全局偏移:        {self.moisture_bias:+.1f}%",
            f"    变异系数:        {self.moisture_var_min:.1f} ~ {self.moisture_var_max:.1f}",
        ]
        return "\n".join(lines)


class WallSegmentSimulator:
    def __init__(
        self,
        cfg: SimConfig,
        segment_id: int,
        segment_name: str,
        base_erosion_rate: float = 0.1,
        base_hardness: float = 2.5,
        local_moisture_factor: float = 1.0,
        local_wind_factor: float = 1.0,
    ):
        self.cfg = cfg
        self.segment_id = segment_id
        self.segment_name = segment_name
        self.base_erosion_rate = base_erosion_rate
        self.base_hardness = base_hardness
        self.local_moisture_factor = local_moisture_factor
        self.local_wind_factor = local_wind_factor
        self.current_erosion_depth = 0.0
        self.hourly_count = 0

        self.erosion_trend = random.uniform(0.8, 1.2)
        self.hardness_decay = random.uniform(0.995, 0.999)
        self.seg_moisture_var = random.uniform(
            cfg.moisture_var_min, cfg.moisture_var_max
        )

    # ============ 风速生成（可配置） ============
    def generate_wind_data(self) -> tuple:
        cfg = self.cfg

        # 季节系数：环境变量SIM_SEASONAL_FACTOR覆盖 > 系统月份自动
        season_factor = cfg.seasonal_factor
        if cfg.seasonal_factor <= 0:  # 设0或负数=使用月份
            month = datetime.now().month
            if month in [3, 4, 5]:
                season_factor = 1.3
            elif month in [6, 7, 8]:
                season_factor = 0.8
            elif month in [12, 1, 2]:
                season_factor = 1.1
            else:
                season_factor = 1.0

        # 昼夜系数
        diurnal_factor = 1.0
        if cfg.diurnal_enable:
            hour = datetime.now().hour
            if 10 <= hour <= 16:
                diurnal_factor = 1.2
            elif 22 <= hour or hour <= 5:
                diurnal_factor = 0.6

        # 基础风速（按配置范围）
        base_speed = random.uniform(cfg.wind_speed_min, cfg.wind_speed_max)

        # 应用系数与偏移
        base_speed = (base_speed * season_factor * diurnal_factor
                      + cfg.wind_speed_bias) * self.local_wind_factor

        # 阵风
        if random.random() < cfg.wind_gust_freq:
            gust = random.choice([1.5, 1.8, 2.0, 2.3])
            wind_speed = base_speed * gust
        else:
            wind_speed = base_speed * random.uniform(0.9, 1.1)

        # 风向（主导风向+扰动）
        if random.random() < 0.7:
            wind_direction = cfg.dominant_wind_dir + random.uniform(-30, 30)
        else:
            wind_direction = random.uniform(0, 360)

        return max(0.1, wind_speed), wind_direction % 360

    # ============ 风蚀深度 ============
    def generate_erosion_depth(self, wind_speed: float) -> float:
        wind_factor = wind_speed ** 2 / 25.0
        hourly_erosion = (self.base_erosion_rate * wind_factor
                          * self.erosion_trend / 8760.0)
        hourly_erosion *= random.uniform(0.8, 1.2)

        self.current_erosion_depth += hourly_erosion
        return max(0.001, self.current_erosion_depth)

    # ============ 含水量（可配置） ============
    def generate_soil_moisture(self) -> float:
        cfg = self.cfg
        month = datetime.now().month

        # 季节自动修正
        season_moist = 1.0
        if month in [7, 8, 9]:
            season_moist = 1.5
        elif month in [12, 1, 2]:
            season_moist = 0.7

        raw = (cfg.moisture_base + cfg.moisture_bias) * self.local_moisture_factor
        moisture = raw * self.seg_moisture_var * season_moist * random.uniform(0.9, 1.1)
        return float(max(0.5, min(30.0, moisture)))

    # ============ 表面硬度 ============
    def generate_surface_hardness(self) -> float:
        self.base_hardness *= self.hardness_decay
        hardness = self.base_hardness * random.uniform(0.95, 1.05)
        return max(0.5, min(5.0, hardness))

    # ============ 传感器数据包 ============
    def generate_sensor_data(self) -> Dict[str, Any]:
        self.hourly_count += 1

        wind_speed, wind_direction = self.generate_wind_data()
        erosion_depth = self.generate_erosion_depth(wind_speed)
        soil_moisture = self.generate_soil_moisture()
        surface_hardness = self.generate_surface_hardness()

        temperature = random.uniform(10.0, 35.0)
        humidity = random.uniform(25.0, 85.0)
        dtu_signal = random.uniform(-85.0, -55.0)

        return {
            "time": datetime.now().isoformat(),
            "segment_id": self.segment_id,
            "sensor_id": f"DTU-{self.segment_id:02d}-{datetime.now().strftime('%Y%m%d%H')}",
            "wind_erosion_depth": round(erosion_depth, 4),
            "soil_moisture": round(soil_moisture, 2),
            "surface_hardness": round(surface_hardness, 3),
            "wind_speed": round(wind_speed, 2),
            "wind_direction": round(wind_direction, 1),
            "temperature": round(temperature, 1),
            "humidity": round(humidity, 1),
            "dtu_signal_strength": round(dtu_signal, 1),
        }

    # ============ 裂缝数据 ============
    def generate_crack_data(self) -> Optional[Dict[str, Any]]:
        if random.random() > 0.08:
            return None
        crack_width = random.uniform(0.1, 5.0)
        extension_rate = crack_width / random.uniform(10.0, 120.0)
        return {
            "time": datetime.now().isoformat(),
            "segment_id": self.segment_id,
            "crack_id": f"CRK-{self.segment_id:02d}-{random.randint(1, 20):02d}",
            "crack_width": round(crack_width, 2),
            "crack_length": round(random.uniform(0.5, 5.0), 2),
            "crack_depth": round(random.uniform(0.1, 0.8), 2),
            "extension_rate": round(extension_rate, 4),
            "location_x": round(random.uniform(0, 1), 3),
            "location_y": round(random.uniform(0, 1), 3),
        }


class DTUSimulator:
    def __init__(self, cfg: SimConfig):
        self.cfg = cfg
        self.segments: List[WallSegmentSimulator] = []
        self._init_segments()

    def _init_segments(self):
        segment_params = [
            # (id, name, erosion_rate, hardness, moisture_factor, wind_factor)
            (1, "西墙北段", 0.08, 2.8, 0.9, 1.2),
            (2, "西墙南段", 0.15, 2.2, 1.0, 1.1),
            (3, "北墙西段", 0.12, 2.5, 0.95, 0.9),
            (4, "北墙东段", 0.06, 3.0, 0.85, 0.85),
            (5, "东墙北段", 0.10, 2.3, 1.1, 1.05),
            (6, "东墙南段", 0.18, 2.0, 1.2, 1.15),
            (7, "南墙西段", 0.09, 2.6, 0.92, 0.95),
            (8, "南墙东段", 0.14, 2.1, 1.05, 1.0),
        ]
        for (sid, name, erosion_rate, hardness, moist_f, wind_f) in segment_params[:self.cfg.num_segments]:
            self.segments.append(WallSegmentSimulator(
                cfg=self.cfg,
                segment_id=sid,
                segment_name=name,
                base_erosion_rate=erosion_rate,
                base_hardness=hardness,
                local_moisture_factor=moist_f,
                local_wind_factor=wind_f,
            ))

    async def send_batch_data(self, data_list: List[Dict[str, Any]]) -> bool:
        try:
            async with httpx.AsyncClient(timeout=60.0) as client:
                response = await client.post(
                    f"{self.cfg.api_url}/api/sensor-data/batch",
                    json=data_list,
                    headers={"Content-Type": "application/json"}
                )
                if response.status_code in [200, 201]:
                    result = response.json()
                    logger.info(f"批量上报成功: {result.get('count', len(data_list))} 条记录")
                    return True
                else:
                    logger.warning(f"批量上报失败: HTTP {response.status_code} - {response.text[:200]}")
                    return False
        except Exception as e:
            logger.warning(f"批量上报异常: {e}")
            return False

    async def send_crack_data(self, crack_data: Dict[str, Any]) -> bool:
        try:
            async with httpx.AsyncClient(timeout=30.0) as client:
                response = await client.post(
                    f"{self.cfg.api_url}/api/wind-field/crack",
                    json=crack_data,
                    headers={"Content-Type": "application/json"}
                )
                return response.status_code in [200, 201]
        except Exception:
            return False

    async def generate_historical_data(self):
        if not self.cfg.generate_historical:
            return
        days = self.cfg.historical_days
        logger.info(f"正在生成 {days} 天历史数据...")

        total_hours = days * 24
        batch_size = 200

        for day in range(days):
            day_data = []
            base_time = datetime.now() - timedelta(days=days - day)

            for hour in range(24):
                current_time = base_time + timedelta(hours=hour)
                for segment in self.segments:
                    data = segment.generate_sensor_data()
                    data["time"] = current_time.isoformat()
                    day_data.append(data)

                    if len(day_data) >= batch_size:
                        await self.send_batch_data(day_data)
                        day_data = []

            if day_data:
                await self.send_batch_data(day_data)

            if (day + 1) % 5 == 0:
                logger.info(f"已生成 {day + 1}/{days} 天历史数据")
            await asyncio.sleep(0.3)

        logger.info("历史数据生成完成")

    async def run_once(self) -> List[Dict[str, Any]]:
        logger.info(f"生成 {len(self.segments)} 个墙段的传感器数据...")

        sensor_data_batch = []
        crack_data_list = []

        for segment in self.segments:
            data = segment.generate_sensor_data()
            sensor_data_batch.append(data)

            crack_data = segment.generate_crack_data()
            if crack_data:
                crack_data_list.append(crack_data)

            logger.info(
                f"[{segment.segment_name:<6}] "
                f"风蚀:{data['wind_erosion_depth']:.4f}mm  "
                f"风速:{data['wind_speed']:.1f}m/s  "
                f"风向:{data['wind_direction']:.0f}°  "
                f"硬度:{data['surface_hardness']:.2f}MPa  "
                f"含水量:{data['soil_moisture']:.1f}%"
            )

        if sensor_data_batch:
            await self.send_batch_data(sensor_data_batch)

        for crack in crack_data_list:
            ok = await self.send_crack_data(crack)
            if ok:
                logger.info(f"裂缝数据上报: {crack['crack_id']} (w={crack['crack_width']}mm)")

        return sensor_data_batch

    async def run_continuous(self):
        logger.info(self.cfg.summary())
        logger.info("=" * 50)
        logger.info("启动连续模拟模式...")

        if self.cfg.generate_historical:
            await self.generate_historical_data()

        while True:
            try:
                await self.run_once()
            except Exception as e:
                logger.error(f"模拟周期异常: {e}")

            logger.info(f"等待 {self.cfg.interval} 秒后下次上报...")
            await asyncio.sleep(self.cfg.interval)


async def main():
    import argparse

    parser = argparse.ArgumentParser(
        description="夯土墙4G DTU传感器模拟器 (风速/含水量可配置)"
    )
    parser.add_argument("--api-url", help="后端API地址 (SIM_API_URL)")
    parser.add_argument("--interval", type=int, help="上报间隔秒 (SIM_INTERVAL)")
    parser.add_argument("--segments", type=int, help="墙段数 (SIM_SEGMENTS)")
    parser.add_argument("--no-historical", action="store_true", help="不生成历史数据")
    parser.add_argument("--historical-days", type=int, help="历史数据天数 (SIM_HISTORICAL_DAYS)")
    parser.add_argument("--once", action="store_true", help="只运行一次")

    # ===== 风速相关CLI =====
    parser.add_argument("--wind-min", type=float, help="最小风速m/s (SIM_WIND_SPEED_MIN)")
    parser.add_argument("--wind-max", type=float, help="最大风速m/s (SIM_WIND_SPEED_MAX)")
    parser.add_argument("--wind-bias", type=float, help="全局风速偏移 (SIM_WIND_SPEED_BIAS)")
    parser.add_argument("--gust-freq", type=float, help="阵风频率0~1 (SIM_WIND_GUST_FREQ)")
    parser.add_argument("--seasonal", type=float, help="季节系数>0, 0=使用月份 (SIM_SEASONAL_FACTOR)")
    parser.add_argument("--no-diurnal", action="store_true", help="禁用昼夜差异")
    parser.add_argument("--dominant-dir", type=float, help="主导风向度数 (SIM_DOMINANT_WIND_DIR)")

    # ===== 含水量相关CLI =====
    parser.add_argument("--moisture", type=float, help="基础含水量%% (SIM_MOISTURE_BASE)")
    parser.add_argument("--moisture-bias", type=float, help="含水量偏移%% (SIM_MOISTURE_BIAS)")
    parser.add_argument("--moisture-var-min", type=float, help="最小变异系数 (SIM_MOISTURE_VAR_MIN)")
    parser.add_argument("--moisture-var-max", type=float, help="最大变异系数 (SIM_MOISTURE_VAR_MAX)")

    args = parser.parse_args()

    # 先创建默认Config，然后用命令行覆盖SIM_*环境变量（注入当前进程env让SimConfig读取）
    if args.wind_min is not None:
        os.environ["SIM_WIND_SPEED_MIN"] = str(args.wind_min)
    if args.wind_max is not None:
        os.environ["SIM_WIND_SPEED_MAX"] = str(args.wind_max)
    if args.wind_bias is not None:
        os.environ["SIM_WIND_SPEED_BIAS"] = str(args.wind_bias)
    if args.gust_freq is not None:
        os.environ["SIM_WIND_GUST_FREQ"] = str(args.gust_freq)
    if args.seasonal is not None:
        os.environ["SIM_SEASONAL_FACTOR"] = str(args.seasonal)
    if args.no_diurnal:
        os.environ["SIM_DIURNAL_ENABLE"] = "false"
    if args.dominant_dir is not None:
        os.environ["SIM_DOMINANT_WIND_DIR"] = str(args.dominant_dir)
    if args.moisture is not None:
        os.environ["SIM_MOISTURE_BASE"] = str(args.moisture)
    if args.moisture_bias is not None:
        os.environ["SIM_MOISTURE_BIAS"] = str(args.moisture_bias)
    if args.moisture_var_min is not None:
        os.environ["SIM_MOISTURE_VAR_MIN"] = str(args.moisture_var_min)
    if args.moisture_var_max is not None:
        os.environ["SIM_MOISTURE_VAR_MAX"] = str(args.moisture_var_max)

    cfg = SimConfig(
        api_url=args.api_url,
        interval=args.interval,
        segments=args.segments,
        generate_historical=not args.no_historical,
        historical_days=args.historical_days,
    )
    simulator = DTUSimulator(cfg)

    if args.once:
        await simulator.run_once()
    else:
        await simulator.run_continuous()


if __name__ == "__main__":
    asyncio.run(main())
