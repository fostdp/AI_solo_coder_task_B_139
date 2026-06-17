import json
import numpy as np
from typing import List, Dict, Any
from pathlib import Path
from backend.services.erosion_model import erosion_simulator


class PlantRootSimulationService:
    def __init__(self):
        config_path = Path(__file__).parent.parent.parent.parent / "config" / "plant_root_params.json"
        with open(config_path, "r", encoding="utf-8") as f:
            self.config = json.load(f)

    def get_available_plants(self) -> List[Dict[str, Any]]:
        plants = self.config.get("plant_species", {})
        result = []
        for code, p in plants.items():
            result.append({
                "code": code,
                "name": p.get("name", code),
                "name_zh": p.get("name_zh", ""),
                "category": p.get("category", ""),
                "root_depth_mm": p.get("root_depth_mm", 0),
                "canopy_coverage_pct": p.get("canopy_coverage_pct", 0),
                "growth_season_months": p.get("growth_season_months", []),
                "protection_score_baseline": p.get("protection", {}).get("erosion_rate_reduction_pct", 0)
            })
        return result

    def _get_seasonal_decay(self, season: str, plant_cfg: Dict) -> float:
        months_map = {"spring": [3, 4, 5], "summer": [6, 7, 8], "autumn": [9, 10, 11], "winter": [12, 1, 2]}
        season_months = months_map.get(season, [6, 7, 8])
        growth = plant_cfg.get("growth_season_months", [])
        overlap = len(set(season_months) & set(growth))
        if overlap >= 2:
            return 1.0
        elif overlap == 1:
            return 0.7
        else:
            return self.config.get("simulation", {}).get("seasonal_decay_factor", 0.3)

    def _calc_single_plant_protection(self, plant_cfg: Dict, coverage_pct: float, season: str) -> Dict[str, float]:
        prot = plant_cfg.get("protection", {})
        plant_max_cov = plant_cfg.get("canopy_coverage_pct", 90)
        eff_cov_ratio = min(1.0, coverage_pct / max(1.0, plant_max_cov))
        seasonal = self._get_seasonal_decay(season, plant_cfg)

        base_erosion_pct = prot.get("erosion_rate_reduction_pct", 0)
        base_wind_red_factor = prot.get("wind_speed_reduction_factor", 0)
        base_coh_inc = prot.get("soil_cohesion_increase_kpa", 0)

        s_curve = 1.0 - np.exp(-3.0 * eff_cov_ratio)
        erosion_reduction = base_erosion_pct * s_curve * seasonal
        wind_reduction_factor = base_wind_red_factor * s_curve * seasonal
        cohesion_increase = base_coh_inc * eff_cov_ratio * seasonal

        return {
            "erosion_reduction_pct": float(erosion_reduction),
            "wind_reduction_factor": float(wind_reduction_factor),
            "wind_reduction_display_pct": float(wind_reduction_factor * 100.0),
            "cohesion_increase_kpa": float(cohesion_increase),
            "effective_coverage_ratio": float(eff_cov_ratio),
            "seasonal_factor": float(seasonal)
        }

    def _calc_combination_bonus(self, plant_set: set) -> float:
        combos = self.config.get("simulation", {}).get("combinations", {})
        has_grass = bool(plant_set & {"GRASS_SHORT", "GRASS_DEEP"})
        has_shrub = "SHRUB" in plant_set
        has_tree = "TREE" in plant_set
        bonus = 0.0
        if has_grass and has_shrub and has_tree:
            bonus = combos.get("all_three", {}).get("erosion_reduction_bonus_pct", 12)
        elif has_shrub and has_tree:
            bonus = max(bonus, combos.get("shrub_tree", {}).get("erosion_reduction_bonus_pct", 6))
        elif has_grass and has_tree:
            bonus = max(bonus, combos.get("grass_tree", {}).get("erosion_reduction_bonus_pct", 8))
        elif has_grass and has_shrub:
            bonus = max(bonus, combos.get("grass_shrub", {}).get("erosion_reduction_bonus_pct", 5))
        return float(bonus)

    def simulate_plant_protection(self, plant_codes: List[str], coverage_pct: float,
                                  wall_height_m: float, wind_speed: float,
                                  soil_moisture: float, season: str = "summer") -> Dict[str, Any]:
        sim_duration = 1.0
        sim_res = erosion_simulator.simulate_two_phase_flow(wind_speed, 180, wall_height_m, soil_moisture, duration_hours=sim_duration)
        avg_depth_mm = sim_res.get("avg_erosion_depth_mm", 0.0)
        baseline_erosion = avg_depth_mm * (365.0 * 24.0 / sim_duration)
        if baseline_erosion < 0.01:
            baseline_erosion = 0.5

        if coverage_pct <= 0 or not plant_codes:
            return {
                "request": {
                    "plant_codes": plant_codes,
                    "coverage_pct": coverage_pct,
                    "wall_height_m": wall_height_m,
                    "wind_speed": wind_speed,
                    "soil_moisture": soil_moisture,
                    "season": season
                },
                "model_used": "simplified_s_curve_v2",
                "baseline_erosion_rate": round(float(baseline_erosion), 4),
                "protected_erosion_rate": round(float(baseline_erosion), 4),
                "total_reduction_pct": 0.0,
                "wind_speed_attenuation_pct_range": [0.0, 0.0],
                "individual_effects": [],
                "combined_bonus_pct": 0.0
            }
        if coverage_pct > 95:
            coverage_pct = 95.0

        plants = self.config.get("plant_species", {})
        individual_effects = []
        max_wind_red_factor = 0.0
        total_cohesion_increase = 0.0
        total_erosion_reduction = 0.0
        valid_codes = []

        for code in plant_codes:
            if code not in plants:
                continue
            valid_codes.append(code)
            p = plants[code]
            eff = self._calc_single_plant_protection(p, coverage_pct, season)
            individual_effects.append({
                "plant_code": code,
                "name": p.get("name", code),
                "name_zh": p.get("name_zh", ""),
                "root_depth_mm": p.get("root_depth_mm", 0),
                "erosion_reduction_pct": round(eff["erosion_reduction_pct"], 2),
                "wind_speed_reduction_pct": round(eff["wind_reduction_display_pct"], 2),
                "cohesion_increase_kpa": round(eff["cohesion_increase_kpa"], 3),
                "seasonal_factor": round(eff["seasonal_factor"], 2),
                "effective_coverage_ratio": round(eff["effective_coverage_ratio"], 3)
            })
            max_wind_red_factor = max(max_wind_red_factor, eff["wind_reduction_factor"])
            total_cohesion_increase += eff["cohesion_increase_kpa"]
            total_erosion_reduction += eff["erosion_reduction_pct"]

        total_erosion_reduction = min(85.0, total_erosion_reduction)
        bonus = self._calc_combination_bonus(set(valid_codes))
        total_reduction_pct = min(95.0, total_erosion_reduction + bonus)

        protected_erosion = baseline_erosion * (1.0 - total_reduction_pct / 100.0)
        wind_attenuation_low = round(max(0.0, max_wind_red_factor * 100.0 * 0.85), 2)
        wind_attenuation_high = round(min(95.0, max_wind_red_factor * 100.0 * 1.1), 2)

        return {
            "request": {
                "plant_codes": plant_codes,
                "coverage_pct": coverage_pct,
                "wall_height_m": wall_height_m,
                "wind_speed": wind_speed,
                "soil_moisture": soil_moisture,
                "season": season
            },
            "model_used": "simplified_s_curve_v2",
            "model_description": "简化S型覆盖率-防护率曲线模型（代替Wu-Waldron复杂根土剪切），叠加季节因子+组合加成",
            "baseline_erosion_rate": round(float(baseline_erosion), 4),
            "protected_erosion_rate": round(float(protected_erosion), 4),
            "total_reduction_pct": round(float(total_reduction_pct), 2),
            "wind_speed_attenuation_pct_range": [wind_attenuation_low, wind_attenuation_high],
            "overall_cohesion_increase_kpa": round(float(total_cohesion_increase), 3),
            "individual_effects": individual_effects,
            "combined_bonus_pct": round(float(bonus), 2)
        }


plant_root_service = PlantRootSimulationService()
