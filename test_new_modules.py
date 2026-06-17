import unittest
import sys
from pathlib import Path

_project_root = Path(__file__).parent.resolve()
if str(_project_root) not in sys.path:
    sys.path.insert(0, str(_project_root))

from backend.modules.craft_comparator.service import dynasty_comparison_service
from backend.modules.era_comparator.service import era_comparison_service
from backend.modules.vegetation_protector.service import plant_root_service
from backend.modules.vr_rammed_earth.service import virtual_experience_service
from backend.modules.craft_comparator.schemas import (
    DynastyComparisonRequest,
    DynastyComparisonResponse,
    DynastyComparisonResult
)
from backend.modules.era_comparator.schemas import (
    CrossEraComparisonRequest,
    CrossEraComparisonResponse,
    CrossEraItem
)
from backend.modules.vegetation_protector.schemas import (
    PlantRootSimulationRequest,
    PlantRootSimulationResponse,
    PlantProtectionEffect
)
from backend.modules.vr_rammed_earth.schemas import (
    MaterialMix,
    VirtualExperienceRequest,
    VirtualExperienceResponse
)


class TestCraftComparatorModule(unittest.TestCase):
    def test_service_exists(self):
        self.assertIsNotNone(dynasty_comparison_service)
        self.assertTrue(hasattr(dynasty_comparison_service, 'compare_dynasties'))
        self.assertTrue(hasattr(dynasty_comparison_service, 'dynasty_config'))

    def test_compare_single_dynasty(self):
        result = dynasty_comparison_service.compare_dynasties(
            ["QIN"], 8.0, 5.0, 24, None
        )
        self.assertIn("results", result)
        self.assertEqual(len(result["results"]), 1)
        self.assertEqual(result["results"][0]["dynasty_code"], "QIN")
        self.assertGreater(result["results"][0]["erosion_rate_mm_per_year"], 0)
        self.assertIn("hardness_mpa", result["results"][0])
        self.assertIn("cohesion_kpa", result["results"][0])

    def test_compare_three_dynasties(self):
        result = dynasty_comparison_service.compare_dynasties(
            ["QIN", "HAN", "MING"], 8.0, 5.0, 24, None
        )
        self.assertEqual(len(result["results"]), 3)
        ranks = [r["rank"] for r in result["results"]]
        self.assertEqual(sorted(ranks), [1, 2, 3])

    def test_climate_scenario(self):
        result_default = dynasty_comparison_service.compare_dynasties(
            ["QIN"], 8.0, 5.0, 24, None
        )
        result_arid = dynasty_comparison_service.compare_dynasties(
            ["QIN"], 8.0, 5.0, 24, "arid"
        )
        self.assertIsNotNone(result_arid["climate_scenario"])
        self.assertNotEqual(
            result_default["climate_scenario"].get("name"),
            result_arid["climate_scenario"].get("name")
        )

    def test_invalid_dynasty(self):
        result = dynasty_comparison_service.compare_dynasties(
            ["INVALID"], 8.0, 5.0, 24, None
        )
        self.assertEqual(len(result["results"]), 0)

    def test_pydantic_schema(self):
        req = DynastyComparisonRequest(dynasty_codes=["QIN", "HAN"])
        self.assertEqual(req.wind_speed, 8.0)
        self.assertEqual(req.duration_hours, 24.0)
        self.assertIsNone(req.climate_scenario)
        self.assertEqual(len(req.dynasty_codes), 2)


class TestEraComparatorModule(unittest.TestCase):
    def test_service_exists(self):
        self.assertIsNotNone(era_comparison_service)
        self.assertTrue(hasattr(era_comparison_service, 'compare_cross_era'))
        self.assertTrue(hasattr(era_comparison_service, 'modern_config'))

    def test_cross_era_both(self):
        result = era_comparison_service.compare_cross_era(
            ["QIN", "HAN"],
            ["CEMENT", "FIBER"],
            8.0, 5.0
        )
        self.assertIn("items", result)
        self.assertIn("ranking", result)
        self.assertEqual(len(result["items"]), 4)
        self.assertEqual(len(result["ranking"]), 4)

    def test_only_ancient(self):
        result = era_comparison_service.compare_cross_era(
            ["QIN", "HAN", "MING"],
            [],
            8.0, 5.0
        )
        self.assertEqual(len(result["items"]), 3)
        ancient_items = [i for i in result["items"] if i["era"] == "ancient"]
        self.assertEqual(len(ancient_items), 3)

    def test_only_modern(self):
        result = era_comparison_service.compare_cross_era(
            [],
            ["CEMENT", "FIBER", "GEOSYNTHETIC"],
            8.0, 5.0
        )
        self.assertEqual(len(result["items"]), 3)
        modern_items = [i for i in result["items"] if i["era"] == "modern"]
        self.assertEqual(len(modern_items), 3)

    def test_topsis_scores_present(self):
        result = era_comparison_service.compare_cross_era(
            ["QIN"],
            ["CEMENT"],
            8.0, 5.0
        )
        for item in result["items"]:
            self.assertIn("topsis_score", item)
            self.assertGreaterEqual(item["topsis_score"], 0)
            self.assertLessEqual(item["topsis_score"], 1)

    def test_cultural_authenticity(self):
        result = era_comparison_service.compare_cross_era(
            ["QIN"],
            ["CEMENT"],
            8.0, 5.0
        )
        ancient = [i for i in result["items"] if i["era"] == "ancient"][0]
        modern = [i for i in result["items"] if i["era"] == "modern"][0]
        self.assertGreater(ancient["cultural_authenticity"], modern["cultural_authenticity"])

    def test_pydantic_schema(self):
        req = CrossEraComparisonRequest(
            include_dynasties=["QIN"],
            include_modern=["CEMENT"],
            wind_speed=10.0
        )
        self.assertEqual(req.wind_speed, 10.0)
        self.assertEqual(len(req.include_dynasties), 1)
        self.assertEqual(len(req.include_modern), 1)


class TestVegetationProtectorModule(unittest.TestCase):
    def test_service_exists(self):
        self.assertIsNotNone(plant_root_service)
        self.assertTrue(hasattr(plant_root_service, 'simulate_plant_protection'))
        self.assertTrue(hasattr(plant_root_service, 'get_available_plants'))

    def test_get_available_plants(self):
        plants = plant_root_service.get_available_plants()
        self.assertGreater(len(plants), 0)
        for p in plants:
            self.assertIn("code", p)
            self.assertIn("name_zh", p)
            self.assertIn("root_depth_mm", p)

    def test_single_grass(self):
        result = plant_root_service.simulate_plant_protection(
            ["GRASS_DEEP"], 70.0, 2.5, 8.0, 5.0, "summer"
        )
        self.assertIn("total_reduction_pct", result)
        self.assertGreater(result["total_reduction_pct"], 0)
        self.assertIn("individual_effects", result)
        self.assertEqual(len(result["individual_effects"]), 1)

    def test_combined_bonus(self):
        result_single = plant_root_service.simulate_plant_protection(
            ["GRASS_DEEP"], 70.0, 2.5, 8.0, 5.0, "summer"
        )
        result_combined = plant_root_service.simulate_plant_protection(
            ["GRASS_DEEP", "SHRUB", "TREE"], 70.0, 2.5, 8.0, 5.0, "summer"
        )
        self.assertGreater(
            result_combined["total_reduction_pct"],
            result_single["total_reduction_pct"]
        )
        self.assertGreater(result_combined["combined_bonus_pct"], 0)

    def test_seasonal_variation(self):
        result_summer = plant_root_service.simulate_plant_protection(
            ["GRASS_DEEP"], 70.0, 2.5, 8.0, 5.0, "summer"
        )
        result_winter = plant_root_service.simulate_plant_protection(
            ["GRASS_DEEP"], 70.0, 2.5, 8.0, 5.0, "winter"
        )
        self.assertGreater(
            result_summer["total_reduction_pct"],
            result_winter["total_reduction_pct"]
        )

    def test_zero_coverage(self):
        result = plant_root_service.simulate_plant_protection(
            ["GRASS_DEEP", "SHRUB"], 0.0, 2.5, 8.0, 5.0, "summer"
        )
        self.assertEqual(result["total_reduction_pct"], 0.0)
        self.assertEqual(len(result["individual_effects"]), 0)

    def test_model_info_present(self):
        result = plant_root_service.simulate_plant_protection(
            ["GRASS_DEEP"], 70.0, 2.5, 8.0, 5.0, "summer"
        )
        self.assertIn("model_used", result)
        self.assertIn("model_description", result)
        self.assertIn("wind_speed_attenuation_pct_range", result)
        self.assertIn("overall_cohesion_increase_kpa", result)

    def test_pydantic_schema(self):
        req = PlantRootSimulationRequest(
            plant_codes=["GRASS_DEEP", "SHRUB"],
            coverage_pct=75.0
        )
        self.assertEqual(req.coverage_pct, 75.0)
        self.assertEqual(req.season, "summer")
        self.assertEqual(req.wall_height_m, 2.5)


class TestVRRammedEarthModule(unittest.TestCase):
    def test_service_exists(self):
        self.assertIsNotNone(virtual_experience_service)
        self.assertTrue(hasattr(virtual_experience_service, 'evaluate_mix'))
        self.assertTrue(hasattr(virtual_experience_service, 'get_dynasty_presets'))
        self.assertTrue(hasattr(virtual_experience_service, 'get_material_presets'))

    def test_standard_mix(self):
        mix = {
            "soil_pct": 65, "clay_pct": 20, "sand_pct": 5,
            "lime_pct": 3, "rice_paste_pct": 2, "straw_pct": 1, "water_pct": 16
        }
        result = virtual_experience_service.evaluate_mix(
            mix, "heavy", 2.5, 8.0
        )
        self.assertIn("quality_score", result)
        self.assertGreater(result["quality_score"], 0)
        self.assertLess(result["quality_score"], 1)
        self.assertIn("quality_rating", result)
        self.assertIn("quality_color", result)

    def test_dynasty_presets_match(self):
        presets = virtual_experience_service.get_dynasty_presets()
        for dcode, dcfg in presets.items():
            mix = dcfg["mix"]
            result = virtual_experience_service.evaluate_mix(
                mix, dcfg.get("tamping", "heavy"), 2.5, 8.0
            )
            self.assertGreater(result["dynasty_match_score"], 0.9)

    def test_qin_preset(self):
        presets = virtual_experience_service.get_dynasty_presets()
        qin = presets["QIN"]["mix"]
        result = virtual_experience_service.evaluate_mix(
            qin, "heavy", 2.5, 8.0
        )
        self.assertEqual(result["dynasty_match"], "QIN")
        self.assertGreater(result["dynasty_match_score"], 0.95)

    def test_water_optimal(self):
        mix_dry = {
            "soil_pct": 65, "clay_pct": 20, "sand_pct": 5,
            "lime_pct": 3, "rice_paste_pct": 2, "straw_pct": 1, "water_pct": 8
        }
        mix_optimal = {
            "soil_pct": 65, "clay_pct": 20, "sand_pct": 5,
            "lime_pct": 3, "rice_paste_pct": 2, "straw_pct": 1, "water_pct": 16
        }
        result_dry = virtual_experience_service.evaluate_mix(mix_dry, "heavy", 2.5, 8.0)
        result_opt = virtual_experience_service.evaluate_mix(mix_optimal, "heavy", 2.5, 8.0)
        self.assertGreater(result_opt["compaction_ratio"], result_dry["compaction_ratio"])

    def test_suggestions_present(self):
        mix = {
            "soil_pct": 65, "clay_pct": 20, "sand_pct": 5,
            "lime_pct": 0, "rice_paste_pct": 0, "straw_pct": 0, "water_pct": 10
        }
        result = virtual_experience_service.evaluate_mix(mix, "light", 2.5, 8.0)
        self.assertGreater(len(result["suggestions"]), 0)

    def test_pydantic_schema(self):
        mix = MaterialMix(soil_pct=60, clay_pct=20, water_pct=16)
        self.assertEqual(mix.soil_pct, 60)
        self.assertEqual(mix.clay_pct, 20)
        self.assertEqual(mix.water_pct, 16)
        req = VirtualExperienceRequest(mix=mix, tamping_preset="heavy")
        self.assertEqual(req.tamping_preset, "heavy")
        self.assertEqual(req.wall_height_m, 2.5)


class TestCrossModuleIntegration(unittest.TestCase):
    def test_era_uses_craft_results(self):
        craft_result = dynasty_comparison_service.compare_dynasties(
            ["QIN"], 8.0, 5.0, 24, None
        )
        era_result = era_comparison_service.compare_cross_era(
            ["QIN"], [], 8.0, 5.0
        )
        craft_erosion = craft_result["results"][0]["erosion_rate_mm_per_year"]
        era_erosion = [i for i in era_result["items"] if i["code"] == "QIN"][0]["erosion_rate_mm_per_year"]
        self.assertAlmostEqual(craft_erosion, era_erosion, places=3)

    def test_vr_erosion_plausible(self):
        presets = virtual_experience_service.get_dynasty_presets()
        qin_mix = presets["QIN"]["mix"]
        vr_result = virtual_experience_service.evaluate_mix(
            qin_mix, "heavy", 2.5, 8.0
        )
        craft_result = dynasty_comparison_service.compare_dynasties(
            ["QIN"], 8.0, 5.0, 24, None
        )
        self.assertGreater(vr_result["erosion_rate_mm_per_year"], 0)
        self.assertGreater(craft_result["results"][0]["erosion_rate_mm_per_year"], 0)


if __name__ == "__main__":
    print("=" * 75)
    print("🧪 新模块重构单元测试")
    print("=" * 75)
    unittest.main(verbosity=2)
