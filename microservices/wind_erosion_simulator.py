import asyncio
import logging
import numpy as np
from datetime import datetime
from typing import Any, Dict, List, Optional, Tuple
from .common import get_erosion_config, get_message_bus, RedisMessageBus

logger = logging.getLogger("wind_erosion_sim")


class WindErosionSimulatorService:
    """
    风沙两相流与风蚀速率计算微服务。
    - 封装所有物理模型：
      * 起动摩阻风速（Shields参数）
      * 摩阻风速廓线
      * 输沙率（Bagnold）
      * 颗粒撞击能量
      * DES湍流增强因子（墙角涡流+流动分离）
    消息模式：request-response（同步/发布
    """

    def __init__(self, bus: RedisMessageBus = None):
        cfg = get_erosion_config()
        self.cfg = cfg
        self.bus = bus
        phys = cfg.get("physical_constants", {})
        des = cfg.get("des_turbulence", {})
        wind = cfg.get("wind_regimes", {})
        self.AIR_DENSITY = phys.get("air_density", 1.225)
        self.SAND_DENSITY = phys.get("sand_density", 2650.0)
        self.GRAVITY = phys.get("gravity", 9.81)
        self.VON_KARMAN = phys.get("von_karman", 0.4)
        self.ROUGHNESS_LENGTH = phys.get("roughness_length", 0.001)
        self.SAND_DIAMETER = phys.get("sand_diameter", 0.0002)
        self.PARTICLE_SHAPE_FACTOR = phys.get("particle_shape_factor", 0.8)
        self.HARDNESS_CORRECTION = phys.get("hardness_correction", 0.001)
        self.MOISTURE_CORRECTION = phys.get("moisture_correction", 0.05)
        self.SHIELDS_PARAMETER = phys.get("shields_parameter", 0.03)
        self.DES_CDES = des.get("c_des", 0.65)
        self.DES_KAPPA = des.get("kappa", 0.41)
        self.RANS_LENGTH_RATIO = des.get("rans_length_ratio", 0.07)
        self.CORNER_VORTEX_STRENGTH = des.get("corner_vortex_strength", 1.8)
        self.REATTACHMENT_LENGTH = des.get("reattachment_length", 2.5)
        self.SEPARATION_ANGLE = des.get("separation_angle_deg", 15.0)
        self.TURBULENCE_ENHANCEMENT = des.get("turbulence_enhancement", 2.5)
        self.BOUNDARY_LAYER_THICKNESS = des.get("boundary_layer_thickness", 0.05)
        self.TRANSPORT_ALPHA = wind.get("transport_coefficient_alpha", 2.0)
        self.IMPACT_VELOCITY_RATIO = wind.get("impact_velocity_ratio", 0.8)

    async def ensure_bus(self):
        if self.bus is None:
            self.bus = await get_message_bus()

    # ============ 物理模型 =================================================
    def calculate_threshold_friction_velocity(self, particle_diameter: float = None) -> float:
        d = particle_diameter or self.SAND_DIAMETER
        return float(
            np.sqrt(
                self.SHIELDS_PARAMETER
                * ((self.SAND_DENSITY - self.AIR_DENSITY)
                / self.AIR_DENSITY
                * self.GRAVITY
                * d
            )
            )
        )

    def calculate_friction_velocity(self, wind_speed: float, height: float = 2.0) -> float:
        return float(
            (wind_speed * self.VON_KARMAN)
            / np.log(height / self.ROUGHNESS_LENGTH)
        )

    def calculate_sand_transport_rate(
        self, u_star: float, u_star_t: float, wind_direction: float = 0
    ) -> float:
        if u_star <= u_star_t:
            return 0.0
        return float(
                self.TRANSPORT_ALPHA
                * self.AIR_DENSITY
                / self.GRAVITY
                * u_star ** 3
                * (1 - (u_star_t / u_star) ** 2)
            )

    def calculate_wind_energy(self, wind_speed: float, duration_hours: float = 1.0) -> float:
        ke_per_vol = 0.5 * self.AIR_DENSITY * wind_speed ** 2
        return float(ke_per_vol * wind_speed * duration_hours * 3600)

    def calculate_particle_impact_energy(
        self, wind_speed: float, particle_mass: float = None
    ) -> float:
        if particle_mass is None:
            particle_mass = (
                (4 / 3)
                * np.pi
                * (self.SAND_DIAMETER / 2) ** 3
                * self.SAND_DENSITY
            )
        v = wind_speed * self.IMPACT_VELOCITY_RATIO
        return float(0.5 * particle_mass * v ** 2)

    def calculate_erosion_rate_from_impact(
        self,
        impact_energy: float,
        surface_hardness: float,
        soil_moisture: float,
        impact_count: float,
    ) -> float:
        hardness_factor = np.exp(-self.HARDNESS_CORRECTION * surface_hardness)
        moisture_factor = np.exp(-self.MOISTURE_CORRECTION * soil_moisture)
        erosion_per_impact = (
            impact_energy
            * self.PARTICLE_SHAPE_FACTOR
            * hardness_factor
            * moisture_factor
            / (surface_hardness * 1e6)
        )
        return float(erosion_per_impact * impact_count)

    def calculate_des_length_scale(
        self, d_wall: float, grid_scale: float, tke: float) -> float:
        l_rans = self.DES_KAPPA * d_wall
        l_les = self.DES_CDES * grid_scale
        return float(max(min(l_rans, l_les), 1e-6))

    def calculate_turbulent_kinetic_energy(
        self, wind_speed: float, turbulence_intensity: float = 0.1
    ) -> float:
        return float(1.5 * (wind_speed * turbulence_intensity) ** 2)

    def calculate_turbulence_dissipation(self, tke: float, length_scale: float) -> float:
        return float(0.09 * tke ** 1.5 / length_scale)

    def calculate_eddy_viscosity(self, tke: float, length_scale: float) -> float:
        return float(0.09 * tke ** 0.5 * length_scale)

    def identify_separation_zone(
        self,
        grid_positions: np.ndarray,
        wall_geometry: Dict[str, Any],
    ) -> np.ndarray:
        if grid_positions.ndim == 1:
            nx, ny = grid_positions.shape
        else:
            nx, ny = grid_positions.shape[:2]
        mask = np.zeros((nx, ny), dtype=bool)
        h = wall_geometry.get("height", 2.0)
        w = wall_geometry.get("width", 3.0)
        angle = np.radians(wall_geometry.get("wind_angle", 0.0))
        for i in range(nx):
            for j in range(ny):
                if grid_positions.ndim == 2:
                    x = grid_positions[i, j, 0]
                    y = grid_positions[i, j, 1]
                else:
                    x, y = grid_positions[i, j, 0], grid_positions[i, j, 1]
                dc = np.sqrt(x ** 2 + y ** 2)
                windward = (x * np.sin(angle) + y * np.cos(angle)) < 0
                dw = abs(dc - w / 2)
                if windward and dw < self.REATTACHMENT_LENGTH * h:
                    mask[i, j] = True
        return mask

    def calculate_corner_vortex_strength(
        self,
        x: float,
        y: float,
        corner: Tuple[float, float],
        wall_height: float,
        wind_speed: float,
    ) -> float:
        dx, dy = x - corner[0], y - corner[1]
        dist = np.sqrt(dx ** 2 + dy ** 2)
        core_radius = self.BOUNDARY_LAYER_THICKNESS * wall_height
        if dist < core_radius:
            return float(self.CORNER_VORTEX_STRENGTH * wind_speed * (dist / core_radius))
        return float(self.CORNER_VORTEX_STRENGTH * wind_speed * (core_radius / max(dist, 1e-6)))

    def calculate_des_erosion_enhancement(
        self,
        distance_to_wall: float,
        wall_distance_norm: float,
        tke: float,
        wind_speed: float,
        separation_zone: bool,
        corner_vortex: bool,
    ) -> float:
        enhancement = 1.0
        if wall_distance_norm < self.BOUNDARY_LAYER_THICKNESS:
            f = 1.0 + (1.0 - wall_distance_norm / self.BOUNDARY_LAYER_THICKNESS)
            enhancement = max(enhancement, f)
        if separation_zone:
            den = max(0.5 * wind_speed ** 2, 1e-6)
            f = 1.0 + self.TURBULENCE_ENHANCEMENT * (tke / den)
            enhancement = max(enhancement, f)
        if corner_vortex:
            enhancement = max(enhancement, self.CORNER_VORTEX_STRENGTH)
        if wall_distance_norm >= self.RANS_LENGTH_RATIO:
            blend = min(1.0, (wall_distance_norm - self.RANS_LENGTH_RATIO) / 0.1)
            enhancement *= 1.0 + blend * 0.3
        return float(enhancement)

    # ============ 高级API =================================================
    def simulate_two_phase_flow_with_des(
        self,
        wind_speed: float,
        wind_direction: float,
        surface_hardness: float,
        soil_moisture: float,
        wall_geometry: Dict[str, Any] = None,
        duration_hours: float = 1.0,
        grid_resolution: int = 20,
    ) -> Dict[str, Any]:
        geometry = wall_geometry or {
            "height": 3.0,
            "width": 40.0,
            "thickness": 2.5,
            "wind_angle": wind_direction,
            "corners": [(-20.0, 0.0), (20.0, 0.0)],
        }
        u_star = self.calculate_friction_velocity(wind_speed)
        u_star_t = self.calculate_threshold_friction_velocity()
        sand_transport = self.calculate_sand_transport_rate(u_star, u_star_t, wind_direction)
        wind_energy = self.calculate_wind_energy(wind_speed, duration_hours)
        impact_energy = self.calculate_particle_impact_energy(wind_speed)
        particle_concentration = sand_transport / max(wind_speed, 0.1)
        base_impact_count = sand_transport * duration_hours * 3600 / max(
            (4 / 3) * np.pi * (self.SAND_DIAMETER / 2) ** 3 * self.SAND_DENSITY,
            1e-9,
        )
        erosion_rate_base = self.calculate_erosion_rate_from_impact(
            impact_energy, surface_hardness, soil_moisture, base_impact_count
        )
        nx = ny = grid_resolution
        h = geometry.get("height", 3.0)
        w = geometry.get("width", 40.0)
        erosion_map = np.zeros((nx, ny))
        enhancement_map = np.ones((nx, ny))
        corners = geometry.get("corners", [(-w / 2, 0.0), (w / 2, 0.0)])
        wind_angle = geometry.get("wind_angle", wind_direction)
        for i in range(nx):
            for j in range(ny):
                x = (i / (nx - 1)) * w - w / 2
                y = (j / (ny - 1)) * geometry.get("thickness", 2.5)
                dw = min(abs(x), abs(y))
                dw_norm = dw / max(h, 1e-6)
                tke = self.calculate_turbulent_kinetic_energy(wind_speed)
                dx = min(np.sqrt((x - c[0]) ** 2 + (y - c[1]) ** 2) for c in corners)
                cv = dx < 0.5
                sz = (abs(x) > w / 4 and abs(y) < 0.5)
                enh = self.calculate_des_erosion_enhancement(dw, dw_norm, tke, wind_speed, sz, cv)
                enhancement_map[i, j] = enh
                erosion_map[i, j] = erosion_rate_base * enh * 1000
        avg_enhancement = float(np.mean(enhancement_map))
        max_erosion = float(np.max(erosion_map))
        avg_erosion = float(np.mean(erosion_map))
        critical_zones = []
        threshold_80 = avg_erosion * 0.8
        for i in range(nx):
            for j in range(ny):
                if erosion_map[i, j] > threshold_80:
                    critical_zones.append(
                        {
                            "grid_x": int(i),
                            "grid_y": int(j),
                            "erosion_mm": float(erosion_map[i, j]),
                            "enhancement": float(enhancement_map[i, j]),
                            "zone_type": (
                                "separation"
                                if enhancement_map[i, j] > 2.0
                                else "corner"
                                if enhancement_map[i, j] > 1.5
                                else "boundary_layer"
                            )
                        }
                    )
        return {
            "friction_velocity": float(u_star),
            "threshold_friction_velocity": float(u_star_t),
            "sand_transport_rate_kg_per_ms": float(sand_transport),
            "wind_energy_joules": float(wind_energy),
            "particle_impact_energy_joules": float(impact_energy),
            "particle_concentration_kg_per_m3": float(particle_concentration),
            "base_erosion_rate_mm_per_year": float(erosion_rate_base * 1000 * 8760),
            "avg_enhancement_factor": float(avg_enhancement),
            "max_erosion_depth_mm": float(max_erosion),
            "avg_erosion_depth_mm": float(avg_erosion),
            "critical_zones": critical_zones[:50],
            "erosion_map_shape": list(erosion_map.shape),
            "des_model_applied": True,
        }

    def simulate_two_phase_flow(
        self,
        wind_speed: float,
        wind_direction: float,
        surface_hardness: float,
        soil_moisture: float,
        duration_hours: float = 1.0,
    ) -> Dict[str, Any]:
        return self.simulate_two_phase_flow_with_des(
            wind_speed, wind_direction, surface_hardness,
            soil_moisture,
            None,
            duration_hours,
        )

    def calculate_long_term_erosion_rate(
        self,
        wind_speeds: np.ndarray,
        wind_directions: np.ndarray,
        surface_hardness: np.ndarray,
        soil_moisture: np.ndarray,
    ) -> Dict[str, Any]:
        if len(wind_speeds) == 0:
            return {
                "erosion_rate_mm_per_year": 0.0,
                "total_erosion_mm": 0.0,
                "max_erosion_depth_mm": 0.0,
                "avg_erosion_depth_mm": 0.0,
                "total_wind_energy": 0.0,
                "total_particle_count": 0,
                "critical_zones": [],
                "erosion_events": [],
            }
        avg_hardness = float(np.mean(surface_hardness))
        avg_moisture = float(np.mean(soil_moisture))
        bins = np.linspace(0, 360, 13)
        erosion_rates = []
        total_energy = 0.0
        total_count = 0
        erosion_events = []
        for k in range(12):
            mask = (wind_directions >= bins[k]) & (wind_directions < bins[k + 1])
            if not np.any(mask):
                continue
            speeds_bin = wind_speeds[mask]
            if len(speeds_bin) == 0:
                continue
            ws = float(np.mean(speeds_bin))
            wd = float((bins[k] + bins[k + 1]) / 2)
            res = self.simulate_two_phase_flow(ws, wd, avg_hardness, avg_moisture, duration_hours=1.0)
            weight = float(np.sum(mask) / len(wind_speeds))
            erosion_rates.append(res["base_erosion_rate_mm_per_year"] * weight)
            total_energy += res["wind_energy_joules"] * weight
            total_count += int(1e6 * weight)
            erosion_events.append(
                {
                    "direction_bin_deg": [float(bins[k]), float(bins[k + 1])],
                    "wind_speed_ms": float(ws),
                    "erosion_rate_mm_per_year": float(
                        res["base_erosion_rate_mm_per_year"]
                    ),
                    "sample_count": int(np.sum(mask)),
                }
            )
        erosion_rate = float(sum(erosion_rates))
        return {
            "erosion_rate_mm_per_year": erosion_rate,
            "total_erosion_mm": erosion_rate,
            "max_erosion_depth_mm": erosion_rate * 2.0,
            "avg_erosion_depth_mm": erosion_rate,
            "total_wind_energy": float(total_energy),
            "total_particle_count": int(total_count),
            "critical_zones": [],
            "erosion_events": erosion_events,
        }

    def generate_wind_field(
        self,
        wind_speed: float,
        wind_direction: float,
        grid_size=(10, 5, 5),
        bounds=(0, 10, 0, 5, 0, 3),
    ) -> List[Dict[str, Any]]:
        x_min, x_max, y_min, y_max, z_min, z_max = bounds
        nx, ny, nz = grid_size
        xs = np.linspace(x_min, x_max, nx)
        ys = np.linspace(y_min, y_max, ny)
        zs = np.linspace(z_min, z_max, nz)
        wd_rad = np.radians(wind_direction)
        base_vx = wind_speed * np.sin(wd_rad)
        base_vy = wind_speed * np.cos(wd_rad)
        field = []
        now = datetime.now().isoformat()
        for i, x in enumerate(xs):
            for j, y in enumerate(ys):
                for k, z in enumerate(zs):
                    hf = np.log(z + 0.001) / np.log(2.0 + 0.001)
                    hf = float(max(0.1, min(1.5, hf)))
                    turb = np.random.normal(0, wind_speed * 0.1, 3)
                    vx = base_vx * hf + turb[0]
                    vy = base_vy * hf + turb[1]
                    vz = wind_speed * 0.05 * hf + turb[2]
                    speed = float(np.sqrt(vx ** 2 + vy ** 2 + vz ** 2))
                    ti = float(np.linalg.norm(turb) / max(speed, 1e-6))
                    particle_conc = speed / max(wind_speed, 0.1) * 0.01
                    field.append(
                        {
                            "time": now,
                            "grid_x": int(i),
                            "grid_y": int(j),
                            "grid_z": int(k),
                            "velocity_x": float(vx),
                            "velocity_y": float(vy),
                            "velocity_z": float(vz),
                            "wind_speed": speed,
                            "wind_direction": float(np.degrees(np.arctan2(vx, vy)) % 360),
                            "turbulence_intensity": ti,
                            "particle_concentration": float(particle_conc),
                        }
                    )
        return field

    # ============ 消息处理 ==================================================
    async def handle_erosion_request(
        self, payload: Dict[str, Any], correlation_id: str
    ):
        try:
            mode = payload.get("mode", "long_term")
            if mode == "two_phase_flow_des":
                result = self.simulate_two_phase_flow_with_des(
                    payload.get("wind_speed", 5.0),
                    payload.get("wind_direction", 180.0),
                    payload.get("surface_hardness", 2.5),
                    payload.get("soil_moisture", 5.0),
                    payload.get("wall_geometry"),
                    payload.get("duration_hours", 1.0),
                    payload.get("grid_resolution", 20),
                )
            elif mode == "wind_field":
                result = {
                    "field_data": self.generate_wind_field(
                        payload.get("wind_speed", 5.0),
                        payload.get("wind_direction", 180.0),
                        tuple(payload.get("grid_size", (10, 5, 5))),
                        tuple(payload.get("bounds", (0, 10, 0, 5, 0, 3))),
                    )
                }
            else:
                ws = np.array(payload.get("wind_speeds", []))
                wd = np.array(payload.get("wind_directions", []))
                hh = np.array(payload.get("hardness", []))
                mm = np.array(payload.get("moisture", []))
                result = self.calculate_long_term_erosion_rate(ws, wd, hh, mm)
            if self.bus:
                await self.bus.publish(
                    RedisMessageBus.CHANNELS["EROSION_RESULT"],
                    {"ok": True, "result": result},
                    correlation_id=correlation_id,
                )
        except Exception as e:
            logger.error(f"Erosion sim error: {e}")
            if self.bus:
                await self.bus.publish(
                    RedisMessageBus.CHANNELS["EROSION_RESULT"],
                    {"ok": False, "error": str(e)},
                    correlation_id=correlation_id,
                )


_simulator: Optional[WindErosionSimulatorService] = None


def get_erosion_simulator() -> WindErosionSimulatorService:
    global _simulator
    if _simulator is None:
        _simulator = WindErosionSimulatorService()
    return _simulator


async def start_wind_erosion_service():
    logging.basicConfig(level=logging.INFO)
    bus = await get_message_bus()
    sim = WindErosionSimulatorService(bus=bus)
    await bus.subscribe(
        RedisMessageBus.CHANNELS["EROSION_REQUEST"],
        sim.handle_erosion_request,
    )
    logger.info("Wind Erosion Simulator microservice started")
    logger.info(f"Subscribed: sim:erosion:request")
    while True:
        await asyncio.sleep(60)


if __name__ == "__main__":
    asyncio.run(start_wind_erosion_service())
