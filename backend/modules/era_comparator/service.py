import json
from typing import List, Dict, Any
from pathlib import Path
from backend.modules.craft_comparator.service import dynasty_comparison_service
from backend.services.topsis_optimizer import topsis_evaluator


class EraComparisonService:
    def __init__(self):
        config_path = Path(__file__).parent.parent.parent.parent / "config" / "dynasty_craft_params.json"
        modern_path = Path(__file__).parent.parent.parent.parent / "config" / "modern_reinforced_soil.json"
        with open(config_path, "r", encoding="utf-8") as f:
            self.dynasty_config = json.load(f)
        with open(modern_path, "r", encoding="utf-8") as f:
            self.modern_config = json.load(f)

    def compare_cross_era(self, dynasty_codes: List[str], modern_codes: List[str],
                          wind_speed: float, soil_moisture: float) -> Dict[str, Any]:
        dynasty_res = dynasty_comparison_service.compare_dynasties(dynasty_codes, wind_speed, soil_moisture, 24, None)
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


era_comparison_service = EraComparisonService()
