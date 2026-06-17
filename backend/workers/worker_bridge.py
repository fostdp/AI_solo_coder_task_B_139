import asyncio
from functools import partial

from backend.services.erosion_model import WindErosionSimulator
from backend.workers.two_phase_flow_worker import TwoPhaseFlowWorkerPool


class WorkerBridge:
    def __init__(self, num_workers: int = None):
        self._num_workers = num_workers
        self._pool: TwoPhaseFlowWorkerPool = None
        self._fallback_simulator: WindErosionSimulator = None

    def _ensure_pool(self):
        if self._pool is None:
            self._pool = TwoPhaseFlowWorkerPool(num_workers=self._num_workers)
            self._pool.start()

    def _ensure_fallback(self):
        if self._fallback_simulator is None:
            self._fallback_simulator = WindErosionSimulator()

    async def _run_via_pool(self, method: str, kwargs: dict) -> dict:
        self._ensure_pool()
        loop = asyncio.get_event_loop()
        task_id = await loop.run_in_executor(None, partial(self._pool.submit, method, kwargs))
        result = await loop.run_in_executor(None, partial(self._pool.get_result, task_id, 30))
        if result.get("error") is not None:
            raise RuntimeError(result["error"])
        return result["result"]

    async def _run_fallback(self, method: str, kwargs: dict) -> dict:
        self._ensure_fallback()
        func = getattr(self._fallback_simulator, method)
        return func(**kwargs)

    async def _dispatch(self, method: str, kwargs: dict) -> dict:
        try:
            return await self._run_via_pool(method, kwargs)
        except Exception:
            return await self._run_fallback(method, kwargs)

    async def async_simulate_two_phase_flow(
        self,
        wind_speed: float,
        wind_direction: float,
        surface_hardness: float,
        soil_moisture: float,
        duration_hours: float = 1.0,
    ) -> dict:
        return await self._dispatch("simulate_two_phase_flow", {
            "wind_speed": wind_speed,
            "wind_direction": wind_direction,
            "surface_hardness": surface_hardness,
            "soil_moisture": soil_moisture,
            "duration_hours": duration_hours,
        })

    async def async_simulate_two_phase_flow_with_des(
        self,
        wind_speed: float,
        wind_direction: float,
        surface_hardness: float,
        soil_moisture: float,
        wall_geometry: dict = None,
        duration_hours: float = 1.0,
        grid_resolution: int = 20,
    ) -> dict:
        kwargs = {
            "wind_speed": wind_speed,
            "wind_direction": wind_direction,
            "surface_hardness": surface_hardness,
            "soil_moisture": soil_moisture,
            "duration_hours": duration_hours,
            "grid_resolution": grid_resolution,
        }
        if wall_geometry is not None:
            kwargs["wall_geometry"] = wall_geometry
        return await self._dispatch("simulate_two_phase_flow_with_des", kwargs)

    async def async_calculate_friction_velocity(self, wind_speed: float, height: float = 2.0) -> dict:
        return await self._dispatch("calculate_friction_velocity", {
            "wind_speed": wind_speed,
            "height": height,
        })

    async def async_calculate_threshold_friction_velocity(
        self,
        particle_diameter: float,
        air_density: float = None,
        sand_density: float = None,
        gravity: float = None,
    ) -> dict:
        kwargs = {"particle_diameter": particle_diameter}
        if air_density is not None:
            kwargs["air_density"] = air_density
        if sand_density is not None:
            kwargs["sand_density"] = sand_density
        if gravity is not None:
            kwargs["gravity"] = gravity
        return await self._dispatch("calculate_threshold_friction_velocity", kwargs)

    async def async_calculate_sand_transport_rate(
        self,
        u_star: float,
        u_star_t: float,
        wind_direction: float,
    ) -> dict:
        return await self._dispatch("calculate_sand_transport_rate", {
            "u_star": u_star,
            "u_star_t": u_star_t,
            "wind_direction": wind_direction,
        })

    async def async_calculate_wind_energy(self, wind_speed: float, duration_hours: float = 1.0) -> dict:
        return await self._dispatch("calculate_wind_energy", {
            "wind_speed": wind_speed,
            "duration_hours": duration_hours,
        })

    async def async_calculate_particle_impact_energy(
        self,
        wind_speed: float,
        particle_mass: float = None,
    ) -> dict:
        kwargs = {"wind_speed": wind_speed}
        if particle_mass is not None:
            kwargs["particle_mass"] = particle_mass
        return await self._dispatch("calculate_particle_impact_energy", kwargs)

    def shutdown(self):
        if self._pool is not None:
            self._pool.shutdown()
            self._pool = None


worker_bridge = WorkerBridge()
