import json
import numpy as np
from typing import List, Dict, Any, Tuple
from pathlib import Path
from .erosion_model import erosion_simulator
from .topsis_optimizer import topsis_evaluator


class DynastyComparisonService:
    def __init__(self):
        config_path = Path(__file__).parent.parent.parent / "config" / "dynasty_craft_params.json"
        modern_path = Path(__file__).parent.parent.parent / "config" / "modern_reinforced_soil.json"
        with open(config_path, "r", encoding="utf-8") as f:
            self.dynasty_config = json.load(f)
        with open(modern_path, "r", encoding="utf-8") as f:
            self.modern_config = json.load(f)

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

    def compare_cross_era(self, dynasty_codes: List[str], modern_codes: List[str],
                          wind_speed: float, soil_moisture: float) -> Dict[str, Any]:
        dynasty_res = self.compare_dynasties(dynasty_codes, wind_speed, soil_moisture, 24, None)
        items = []
        for dr in dynasty_res["results"]:
            items.append({
                "code": dr["dynasty_code"],
                "name": dr["name"],
                "era": "ancient",
                "erosion_rate_mm_per_year": dr["erosion_rate_mm_per_year"],
                "hardness_mpa": dr["hardness_mpa"],
                "cohesion_kpa": dr["cohesion_kpa"],
                "environmental_impact": 0.10,
                "reversibility": 0.90,
                "cultural_authenticity": 1.00
            })
        modern = self.modern_config.get("modern_reinforced_soil", {})
        for code in modern_codes:
            if code not in modern:
                continue
            m = modern[code]
            props = m.get("erosion_properties_std", m.get("erosion_properties", {}))
            hard_mult = props.get("hardness_multiplier", 1.0)
            eros_mod = props.get("erosion_rate_modifier", 1.0)
            cohesion = props.get("surface_cohesion_kpa", 50.0)
            base_eros_ref = dynasty_res["results"][0]["erosion_rate_mm_per_year"] if dynasty_res["results"] else 0.5
            erosion_rate = base_eros_ref * eros_mod
            hardness = 2.5 * hard_mult
            cross_metrics = m.get("cross_era_metrics_std", {})
            items.append({
                "code": code,
                "name": m.get("name", code),
                "era": "modern",
                "standard_reference": m.get("standard_reference", ""),
                "erosion_rate_mm_per_year": round(float(erosion_rate), 4),
                "hardness_mpa": round(float(hardness), 3),
                "cohesion_kpa": round(float(cohesion), 2),
                "environmental_impact": cross_metrics.get("environmental_compatibility_score", 0.4),
                "reversibility": cross_metrics.get("reversibility_score", 0.3),
                "cultural_authenticity": cross_metrics.get("cultural_authenticity_score", 0.10),
                "construction_efficiency": cross_metrics.get("construction_efficiency_score", 0.7),
                "cost_efficiency": cross_metrics.get("cost_efficiency_score", 0.7),
                "durability_years_est": cross_metrics.get("durability_years_est", 50),
                "carbon_footprint_kg_co2": m.get("parameters", {}).get("carbon_footprint_kg_co2_per_m3", 0),
                "cost_yuan_per_m3": m.get("parameters", {}).get("cost_yuan_per_m3", 0)
            })
        criteria = ["erosion_rate_mm_per_year", "hardness_mpa", "cohesion_kpa",
                    "environmental_impact", "reversibility", "cultural_authenticity",
                    "construction_efficiency", "cost_efficiency"]
        metric_cfg = self.modern_config.get("comparison_metrics", {})
        w_cfg = metric_cfg.get("weights_v1_std", metric_cfg.get("weights", {
            "erosion_resistance": 0.30, "environmental_compatibility": 0.20,
            "reversibility": 0.15, "cost_efficiency": 0.15, "cultural_authenticity": 0.20
        }))
        weights = {
            "erosion_rate_mm_per_year": w_cfg.get("erosion_resistance", 0.25),
            "hardness_mpa": 0.12,
            "cohesion_kpa": 0.10,
            "environmental_impact": w_cfg.get("environmental_compatibility", 0.15),
            "reversibility": w_cfg.get("reversibility", 0.13),
            "cultural_authenticity": w_cfg.get("cultural_authenticity", 0.15),
            "construction_efficiency": 0.07,
            "cost_efficiency": w_cfg.get("cost_efficiency", 0.08)
        }
        benefit = ["hardness_mpa", "cohesion_kpa", "reversibility", "cultural_authenticity",
                   "construction_efficiency", "cost_efficiency"]
        cost = ["erosion_rate_mm_per_year", "environmental_impact"]
        try:
            matrix = []
            for it in items:
                matrix.append([it[c] for c in criteria])
            scores = topsis_evaluator.evaluate(matrix, [weights.get(c, 0.1667) for c in criteria],
                                               benefit, cost)
            for i, it in enumerate(items):
                it["topsis_score"] = round(float(scores[i]), 4)
        except Exception:
            for it in items:
                it["topsis_score"] = 0.5
        items.sort(key=lambda it: it.get("topsis_score", 0.0), reverse=True)
        ranking = [{"rank": i + 1, "code": it["code"], "name": it["name"], "topsis_score": it.get("topsis_score", 0.0)}
                   for i, it in enumerate(items)]
        return {"items": items, "ranking": ranking}


dynasty_comparison_service = DynastyComparisonService()
