import unittest
import sys
import asyncio
from pathlib import Path

_project_root = Path(__file__).parent.resolve()
if str(_project_root) not in sys.path:
    sys.path.insert(0, str(_project_root))


class TestTwoPhaseFlowWorker(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        from backend.workers.two_phase_flow_worker import TwoPhaseFlowWorkerPool
        cls.pool = TwoPhaseFlowWorkerPool(num_workers=2)
        cls.pool.start()

    @classmethod
    def tearDownClass(cls):
        cls.pool.shutdown()

    def test_friction_velocity(self):
        task_id = self.pool.submit("calculate_friction_velocity", {"wind_speed": 10.0})
        result = self.pool.get_result(task_id, timeout=10)
        self.assertIsNone(result["error"])
        self.assertAlmostEqual(result["result"], 0.526, places=2)

    def test_threshold_friction_velocity(self):
        task_id = self.pool.submit("calculate_threshold_friction_velocity", {
            "particle_diameter": 0.0003
        })
        result = self.pool.get_result(task_id, timeout=10)
        self.assertIsNone(result["error"])
        self.assertGreater(result["result"], 0)

    def test_sand_transport_rate(self):
        u_star = 0.5
        u_star_t = 0.2
        task_id = self.pool.submit("calculate_sand_transport_rate", {
            "u_star": u_star,
            "u_star_t": u_star_t,
            "wind_direction": 45.0
        })
        result = self.pool.get_result(task_id, timeout=10)
        self.assertIsNone(result["error"])
        self.assertGreater(result["result"], 0)

    def test_simulate_two_phase_flow(self):
        task_id = self.pool.submit("simulate_two_phase_flow", {
            "wind_speed": 8.0,
            "wind_direction": 45.0,
            "surface_hardness": 5.0,
            "soil_moisture": 5.0,
            "duration_hours": 1.0
        })
        result = self.pool.get_result(task_id, timeout=15)
        self.assertIsNone(result["error"])
        data = result["result"]
        self.assertIn("erosion_grid", data)
        self.assertIn("tke_grid", data)
        self.assertIn("avg_erosion_depth_mm", data)
        self.assertIn("max_erosion_depth_mm", data)
        self.assertGreater(data["avg_erosion_depth_mm"], 0)

    def test_simulate_two_phase_flow_with_des(self):
        wall_geom = {"height_m": 2.5, "length_m": 10.0, "width_m": 0.8}
        task_id = self.pool.submit("simulate_two_phase_flow_with_des", {
            "wind_speed": 8.0,
            "wind_direction": 0.0,
            "surface_hardness": 3.5,
            "soil_moisture": 5.0,
            "wall_geometry": wall_geom,
            "duration_hours": 0.5,
            "grid_resolution": 10
        })
        result = self.pool.get_result(task_id, timeout=20)
        self.assertIsNone(result["error"])
        data = result["result"]
        self.assertIn("avg_erosion_depth_mm", data)
        self.assertIn("des_regions", data)
        self.assertGreater(data["avg_erosion_depth_mm"], 0)

    def test_multiple_concurrent_tasks(self):
        ids = []
        for i in range(4):
            tid = self.pool.submit("calculate_friction_velocity", {"wind_speed": 5.0 + i})
            ids.append(tid)
        results = [self.pool.get_result(tid, timeout=10) for tid in ids]
        self.assertEqual(len(results), 4)
        for r in results:
            self.assertIsNone(r["error"])
            self.assertGreater(r["result"], 0)

    def test_invalid_method(self):
        task_id = self.pool.submit("nonexistent_method", {"x": 1})
        result = self.pool.get_result(task_id, timeout=10)
        self.assertIsNotNone(result["error"])


class TestWorkerBridge(unittest.TestCase):
    def setUp(self):
        from backend.workers.worker_bridge import WorkerBridge
        self.bridge = WorkerBridge(num_workers=1)

    def tearDown(self):
        self.bridge.shutdown()

    def test_bridge_async_friction(self):
        async def _run():
            result = await self.bridge.async_calculate_friction_velocity(
                wind_speed=12.0
            )
            return result
        result = asyncio.run(_run())
        self.assertGreater(result, 0)

    def test_bridge_async_simulate(self):
        async def _run():
            result = await self.bridge.async_simulate_two_phase_flow(
                wind_speed=10.0,
                wind_direction=90.0,
                surface_hardness=4.0,
                soil_moisture=6.0,
                duration_hours=0.5
            )
            return result
        result = asyncio.run(_run())
        self.assertIn("avg_erosion_depth_mm", result)
        self.assertGreater(result["avg_erosion_depth_mm"], 0)

    def test_bridge_fallback_mode(self):
        async def _run():
            return await self.bridge._run_fallback(
                "calculate_friction_velocity",
                {"wind_speed": 10.0}
            )
        result = asyncio.run(_run())
        self.assertAlmostEqual(result, 0.526, places=2)


if __name__ == "__main__":
    print("=" * 75)
    print("Two-phase flow Worker tests")
    print("=" * 75)
    unittest.main(verbosity=2)
