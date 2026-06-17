import json
import numpy as np
from typing import Dict, Any, List
from pathlib import Path
from .erosion_model import erosion_simulator


class VirtualExperienceService:
    def __init__(self):
        config_path = Path(__file__).parent.parent.parent / "config" / "virtual_experience_params.json"
        with open(config_path, "r", encoding="utf-8") as f:
            self.config = json.load(f)

    def get_material_presets(self) -> Dict[str, Any]:
        return {
            "base_materials": self.config.get("base_materials", {}),
            "tamping_presets": self.config.get("tamping_presets", {})
        }

    def get_dynasty_presets(self) -> Dict[str, Any]:
        return {
            "QIN": {
                "name": "秦代版筑夯土",
                "mix": {"soil_pct": 68, "clay_pct": 25, "sand_pct": 5, "lime_pct": 0, "rice_paste_pct": 3, "straw_pct": 0, "water_pct": 16},
                "tamping": "heavy",
                "description": "高密度版筑，糯米汁粘结，抗风蚀能力最强"
            },
            "HAN": {
                "name": "汉代草拌夯土",
                "mix": {"soil_pct": 65, "clay_pct": 22, "sand_pct": 7, "lime_pct": 0, "rice_paste_pct": 1, "straw_pct": 5, "water_pct": 18},
                "tamping": "medium",
                "description": "掺麦草纤维增强抗拉，抗裂性好"
            },
            "MING": {
                "name": "明代三合土",
                "mix": {"soil_pct": 60, "clay_pct": 20, "sand_pct": 12, "lime_pct": 8, "rice_paste_pct": 0, "straw_pct": 0, "water_pct": 15},
                "tamping": "heavy",
                "description": "石灰胶凝，防水性强，耐久性好"
            }
        }

    def _get_quality_rating(self, score: float) -> Dict[str, str]:
        ratings = self.config.get("quality_ratings", {})
        for key in ["excellent", "good", "fair", "poor", "bad"]:
            r = ratings.get(key, {})
            if score >= r.get("min_score", 0):
                return {"rating": r.get("label", key), "color": r.get("color", "#888")}
        return {"rating": "劣", "color": "#d73027"}

    def _match_dynasty(self, mix: Dict[str, float]) -> Dict[str, Any]:
        dynasty_presets = self.get_dynasty_presets()
        best = None
        best_score = 0.0
        for dcode, dcfg in dynasty_presets.items():
            dmix = dcfg["mix"]
            sim = 0.0
            n = 0
            for k in ["soil_pct", "clay_pct", "sand_pct", "lime_pct", "rice_paste_pct", "straw_pct", "water_pct"]:
                max_val = 80.0
                diff = abs(mix.get(k, 0) - dmix.get(k, 0))
                sim += max(0.0, 1.0 - diff / max_val)
                n += 1
            sim = sim / max(1, n)
            if sim > best_score:
                best_score = sim
                best = dcode
        return {"dynasty_match": best or "QIN", "dynasty_match_score": round(float(best_score), 4)}

    def evaluate_mix(self, mix_dict: Dict[str, float], tamping_preset: str,
                     wall_height_m: float, wind_speed: float) -> Dict[str, Any]:
        materials = self.config.get("base_materials", {})
        mix_map = {
            "soil": mix_dict.get("soil_pct", 0),
            "clay": mix_dict.get("clay_pct", 0),
            "sand": mix_dict.get("sand_pct", 0),
            "lime": mix_dict.get("lime_pct", 0),
            "rice_paste": mix_dict.get("rice_paste_pct", 0),
            "straw": mix_dict.get("straw_pct", 0)
        }
        erosion_rate = 0.5
        hardness = 2.5
        cohesion = 50.0
        crack_resistance = 1.0
        for mname, pct in mix_map.items():
            mcfg = materials.get(mname, {})
            eff = mcfg.get("effect", {})
            erosion_rate += pct * eff.get("erosion_rate_per_pct", 0)
            hardness += pct * eff.get("hardness_per_pct", 0)
            cohesion += pct * eff.get("cohesion_per_pct", 0)
            if mname == "straw":
                crack_resistance += pct * eff.get("crack_resistance_bonus", 0)
        water = mix_dict.get("water_pct", 16)
        water_cfg = materials.get("water", {}).get("effect", {})
        opt_range = water_cfg.get("optimal_range", [14, 18])
        water_mod = 1.0
        if opt_range[0] <= water <= opt_range[1]:
            water_mod = 1.0
        elif water < opt_range[0]:
            water_mod = 1.0 - water_cfg.get("too_dry_penalty", 0.3) * (opt_range[0] - water) / max(1.0, opt_range[0] - 8)
        else:
            water_mod = 1.0 - water_cfg.get("too_wet_penalty", 0.4) * (water - opt_range[1]) / max(1.0, 22 - opt_range[1])
        water_mod = max(0.5, min(1.0, water_mod))
        tamping = self.config.get("tamping_presets", {}).get(tamping_preset, self.config["tamping_presets"]["heavy"])
        compaction_factor = tamping.get("compaction_factor", 0.9)
        moisture_resistance = 1.0 + (mix_dict.get("lime_pct", 0) * 0.02 + mix_dict.get("rice_paste_pct", 0) * 0.03)
        compaction_ratio = min(0.99, 0.8 * compaction_factor * water_mod)
        sim_duration = 1.0
        sim_res = erosion_simulator.simulate_two_phase_flow(wind_speed, 180, wall_height_m, mix_dict.get("water_pct", 16), duration_hours=sim_duration)
        avg_depth_mm = sim_res.get("avg_erosion_depth_mm", 0.0)
        base_sim_rate = avg_depth_mm * (365.0 * 24.0 / sim_duration)
        if base_sim_rate < 0.05:
            base_sim_rate = 0.5
        final_erosion = max(0.05, base_sim_rate * (erosion_rate / 0.5) / moisture_resistance * (1.0 - compaction_ratio * 0.3))
        final_hardness = max(0.5, hardness * compaction_ratio * 2.0)
        final_cohesion = max(10, cohesion * compaction_ratio)
        norm_erosion = max(0.0, min(1.0, 1.0 - final_erosion / 2.0))
        norm_hard = max(0.0, min(1.0, final_hardness / 5.0))
        norm_coh = max(0.0, min(1.0, final_cohesion / 100.0))
        quality_score = norm_erosion * 0.30 + norm_hard * 0.25 + norm_coh * 0.25 + compaction_ratio * 0.20
        rating_info = self._get_quality_rating(quality_score)
        match_info = self._match_dynasty(mix_dict)
        suggestions = []
        if compaction_ratio < 0.8:
            suggestions.append("夯实度偏低，建议增加夯打力度或调整含水量至最优区间")
        if water < 14:
            suggestions.append("含水量偏低，土料偏干，颗粒粘结性下降")
        if water > 18:
            suggestions.append("含水量偏高，土料过湿，夯实时容易产生弹簧现象")
        if mix_dict.get("lime_pct", 0) < 3 and mix_dict.get("rice_paste_pct", 0) < 2:
            suggestions.append("可适当添加石灰或糯米汁以提升胶结性能")
        if mix_dict.get("straw_pct", 0) < 1 and mix_dict.get("clay_pct", 0) > 20:
            suggestions.append("建议掺入少量麦草纤维以提升抗裂性")
        if erosion_rate < 0.3:
            suggestions.append("侵蚀率控制良好，耐久性优秀")
        if not suggestions:
            suggestions.append("材料配比合理，夯实度充足，整体质量良好")
        return {
            "mix": mix_dict,
            "tamping_preset": tamping_preset,
            "compaction_ratio": round(float(compaction_ratio), 4),
            "quality_score": round(float(quality_score), 4),
            "quality_rating": rating_info["rating"],
            "quality_color": rating_info["color"],
            "erosion_rate_mm_per_year": round(float(final_erosion), 4),
            "hardness_mpa": round(float(final_hardness), 3),
            "cohesion_kpa": round(float(final_cohesion), 2),
            "crack_resistance": round(float(crack_resistance), 3),
            "moisture_resistance": round(float(moisture_resistance), 3),
            "dynasty_match": match_info["dynasty_match"],
            "dynasty_match_score": match_info["dynasty_match_score"],
            "suggestions": suggestions
        }


virtual_experience_service = VirtualExperienceService()
