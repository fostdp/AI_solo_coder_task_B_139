import json
import numpy as np
from typing import List, Dict, Any
from pathlib import Path
from .erosion_model import erosion_simulator


class PlantRootSimulationService:
    def __init__(self):
        config_path = Path(__file__).parent.parent.parent / "config" / "plant_root_params.json"
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
                "growth_season_months": p.get("growth_season_months", [])
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
                "baseline_erosion_rate": round(float(baseline_erosion), 4),
                "protected_erosion_rate": round(float(baseline_erosion), 4),
                "total_reduction_pct": 0.0,
                "individual_effects": [],
                "combined_bonus_pct": 0.0
            }
        if coverage_pct > 95:
            coverage_pct = 95.0
        plants = self.config.get("plant_species", {})
        individual_effects = []
        total_wind_reduction = 0.0
        total_cohesion_increase = 0.0
        total_erosion_reduction = 0.0
        total_moisture_retention = 0.0
        max_coverage = self.config.get("simulation", {}).get("max_coverage_pct", 90)
        for code in plant_codes:
            if code not in plants:
                continue
            p = plants[code]
            prot = p.get("protection", {})
            plant_max_cov = p.get("canopy_coverage_pct", max_coverage)
            eff_cov = min(coverage_pct, plant_max_cov) / 100.0
            seasonal = self._get_seasonal_decay(season, p)
            coh_inc = prot.get("soil_cohesion_increase_kpa", 0) * eff_cov * seasonal
            wind_red = prot.get("wind_speed_reduction_factor", 0) * eff_cov * seasonal
            eros_red = prot.get("erosion_rate_reduction_pct", 0) * eff_cov * seasonal
            moist_ret = prot.get("moisture_retention_factor", 0) * eff_cov * seasonal
            bind = prot.get("surface_binding_strength", 0) * eff_cov * seasonal
            individual_effects.append({
                "plant_code": code,
                "name": p.get("name", code),
                "soil_cohesion_increase_kpa": round(float(coh_inc), 3),
                "wind_speed_reduction_pct": round(float(wind_red * 100), 2),
                "erosion_rate_reduction_pct": round(float(eros_red), 2),
                "moisture_retention_pct": round(float(moist_ret * 100), 2),
                "surface_binding": round(float(bind), 3)
            })
            total_wind_reduction = max(total_wind_reduction, wind_red)
            total_cohesion_increase += coh_inc
            total_erosion_reduction += eros_red
            total_moisture_retention = max(total_moisture_retention, moist_ret)
        combos = self.config.get("simulation", {}).get("combinations", {})
        bonus = 0.0
        plant_set = set(plant_codes)
        for cname, ccfg in combos.items():
            if cname == "grass_shrub" and {"GRASS_SHORT", "GRASS_DEEP", "SHRUB"} & plant_set:
                if "SHRUB" in plant_set and (plant_set & {"GRASS_SHORT", "GRASS_DEEP"}):
                    bonus = max(bonus, ccfg.get("erosion_reduction_bonus_pct", 0))
            elif cname == "grass_tree" and "TREE" in plant_set and (plant_set & {"GRASS_SHORT", "GRASS_DEEP"}):
                bonus = max(bonus, ccfg.get("erosion_reduction_bonus_pct", 0))
            elif cname == "shrub_tree" and "TREE" in plant_set and "SHRUB" in plant_set:
                bonus = max(bonus, ccfg.get("erosion_reduction_bonus_pct", 0))
            elif cname == "all_three" and len(plant_set & {"GRASS_SHORT", "GRASS_DEEP", "SHRUB", "TREE"}) >= 3:
                bonus = max(bonus, ccfg.get("erosion_reduction_bonus_pct", 0))
        total_reduction = min(95.0, total_erosion_reduction + bonus)
        protected_erosion = baseline_erosion * (1.0 - total_reduction / 100.0)
        return {
            "request": {
                "plant_codes": plant_codes,
                "coverage_pct": coverage_pct,
                "wall_height_m": wall_height_m,
                "wind_speed": wind_speed,
                "soil_moisture": soil_moisture,
                "season": season
            },
            "baseline_erosion_rate": round(float(baseline_erosion), 4),
            "protected_erosion_rate": round(float(protected_erosion), 4),
            "total_reduction_pct": round(float(total_reduction), 2),
            "individual_effects": individual_effects,
            "combined_bonus_pct": round(float(bonus), 2)
        }


plant_root_service = PlantRootSimulationService()
