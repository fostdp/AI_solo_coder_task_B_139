import json
from typing import List, Dict, Any, Tuple
from pathlib import Path
from backend.services.erosion_model import erosion_simulator


class DynastyComparisonService:
    def __init__(self):
        config_path = Path(__file__).parent.parent.parent.parent / "config" / "dynasty_craft_params.json"
        with open(config_path, "r", encoding="utf-8") as f:
            self.dynasty_config = json.load(f)

    def _apply_climate_scenario(self, scenario: str, wind_speed: float, soil_moisture: float) -> Tuple[float, float, Dict[str, Any]]:
        if not scenario:
            return wind_speed, soil_moisture, {"name": "default", "description": "默认气候"}
        scenarios = self.dynasty_config.get("simulation", {}).get("climate_scenarios", {})
        if scenario not in scenarios:
            return wind_speed, soil_moisture, {"name": "default", "description": "默认气候"}
        s = scenarios[scenario]
        adj_wind = s.get("avg_wind", wind_speed)
        adj_moist = s.get("avg_moisture", soil_moisture)
        return adj_wind, adj_moist, s

    def compare_dynasties(self, dynasty_codes: List[str], wind_speed: float, soil_moisture: float,
                          duration_hours: float, climate_scenario: str = None) -> Dict[str, Any]:
        ws, sm, scenario_info = self._apply_climate_scenario(climate_scenario, wind_speed, soil_moisture)
        sim_duration = 1.0
        sim_res = erosion_simulator.simulate_two_phase_flow(ws, 180, 2.5, sm, duration_hours=sim_duration)
        avg_depth_mm = sim_res.get("avg_erosion_depth_mm", 0.0)
        base_erosion_rate = avg_depth_mm * (365.0 * 24.0 / sim_duration)
        base_max_depth = sim_res.get("max_erosion_depth_mm", 0.0)
        if base_erosion_rate < 0.01:
            base_erosion_rate = 0.01
        dynasties = self.dynasty_config.get("dynasties", {})
        results = []
        for code in dynasty_codes:
            if code not in dynasties:
                continue
            dyn = dynasties[code]
            props = dyn.get("erosion_properties", {})
            hard_mult = props.get("hardness_multiplier", 1.0)
            eros_mod = props.get("erosion_rate_modifier", 1.0)
            moist_res = props.get("moisture_resistance", 1.0)
            cohesion = props.get("surface_cohesion_kpa", 50.0)
            erosion_rate = base_erosion_rate * eros_mod * (1.0 / moist_res)
            max_depth = base_max_depth * eros_mod
            hardness = 2.5 * hard_mult
            norm_erosion = max(0.0, min(1.0, 1.0 - erosion_rate / 2.0))
            norm_hard = max(0.0, min(1.0, hardness / 5.0))
            norm_cohesion = max(0.0, min(1.0, cohesion / 100.0))
            overall_score = norm_erosion * 0.3 + norm_hard * 0.2 + norm_cohesion * 0.2 + moist_res * 0.3
            results.append({
                "dynasty_code": code,
                "name": dyn.get("name", code),
                "erosion_rate_mm_per_year": round(float(erosion_rate), 4),
                "max_erosion_depth_mm": round(float(max_depth), 4),
                "hardness_mpa": round(float(hardness), 3),
                "cohesion_kpa": round(float(cohesion), 2),
                "moisture_resistance": round(float(moist_res), 3),
                "overall_score": round(float(overall_score), 4)
            })
        results.sort(key=lambda r: r["overall_score"], reverse=True)
        for i, r in enumerate(results):
            r["rank"] = i + 1
        return {
            "request": {
                "dynasty_codes": dynasty_codes,
                "wind_speed": ws,
                "soil_moisture": sm,
                "duration_hours": duration_hours,
                "climate_scenario": climate_scenario
            },
            "results": results,
            "climate_scenario": scenario_info
        }


dynasty_comparison_service = DynastyComparisonService()
