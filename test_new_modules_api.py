import unittest
import sys
from pathlib import Path

_project_root = Path(__file__).parent.resolve()
if str(_project_root) not in sys.path:
    sys.path.insert(0, str(_project_root))

from fastapi.testclient import TestClient
from backend.main import app

client = TestClient(app)


class TestCraftComparatorAPI(unittest.TestCase):
    def test_craft_compare_post(self):
        response = client.post(
            "/api/dynasty/compare",
            json={
                "dynasty_codes": ["QIN", "HAN", "MING"],
                "wind_speed": 10.0
            }
        )
        self.assertEqual(response.status_code, 200)
        data = response.json()
        self.assertEqual(len(data["results"]), 3)
        ranks = [r["rank"] for r in data["results"]]
        self.assertEqual(sorted(ranks), [1, 2, 3])

    def test_craft_list(self):
        response = client.get("/api/dynasty/list")
        self.assertEqual(response.status_code, 200)
        data = response.json()
        self.assertIn("dynasties", data)
        self.assertIn("climate_scenarios", data)
        self.assertGreater(len(data["dynasties"]), 0)
        for d in data["dynasties"]:
            self.assertIn("code", d)
            self.assertIn("name", d)
            self.assertIn("compaction_ratio", d)


class TestEraComparatorAPI(unittest.TestCase):
    def test_cross_era_compare_both(self):
        response = client.post(
            "/api/cross-era/compare",
            json={
                "include_dynasties": ["QIN", "HAN"],
                "include_modern": ["CEMENT", "FIBER"],
                "wind_speed": 8.0
            }
        )
        self.assertEqual(response.status_code, 200)
        data = response.json()
        self.assertIn("items", data)
        self.assertEqual(len(data["items"]), 4)
        self.assertIn("ranking", data)
        self.assertEqual(len(data["ranking"]), 4)

    def test_cross_era_only_ancient(self):
        response = client.post(
            "/api/cross-era/compare",
            json={
                "include_dynasties": ["QIN", "HAN", "MING"],
                "include_modern": [],
                "wind_speed": 8.0
            }
        )
        self.assertEqual(response.status_code, 200)
        data = response.json()
        self.assertEqual(len(data["items"]), 3)
        ancient = [i for i in data["items"] if i["era"] == "ancient"]
        self.assertEqual(len(ancient), 3)

    def test_cross_era_cultural_authenticity(self):
        response = client.post(
            "/api/cross-era/compare",
            json={
                "include_dynasties": ["QIN"],
                "include_modern": ["CEMENT"],
                "wind_speed": 8.0
            }
        )
        data = response.json()
        ancient = [i for i in data["items"] if i["era"] == "ancient"][0]
        modern = [i for i in data["items"] if i["era"] == "modern"][0]
        self.assertGreater(
            ancient["cultural_authenticity"], modern["cultural_authenticity"])

    def test_cross_era_topsis_scores(self):
        response = client.post(
            "/api/cross-era/compare",
            json={
                "include_dynasties": ["QIN"],
                "include_modern": ["CEMENT"],
                "wind_speed": 8.0
            }
        )
        data = response.json()
        for item in data["items"]:
            self.assertIn("topsis_score", item)
            self.assertGreaterEqual(item["topsis_score"], 0)
            self.assertLessEqual(item["topsis_score"], 1)


class TestVegetationProtectorAPI(unittest.TestCase):
    def test_plant_species_list(self):
        response = client.get("/api/plants/species")
        self.assertEqual(response.status_code, 200)
        data = response.json()
        self.assertIn("plants", data)
        self.assertGreater(len(data["plants"]), 0)

    def test_plant_simulate_single(self):
        response = client.post(
            "/api/plants/simulate",
            json={
                "plant_codes": ["GRASS_DEEP"],
                "coverage_pct": 70.0,
                "season": "summer"
            }
        )
        self.assertEqual(response.status_code, 200)
        data = response.json()
        self.assertIn("total_reduction_pct", data)
        self.assertGreater(data["total_reduction_pct"], 0)
        self.assertIn("model_used", data)

    def test_plant_simulate_combined(self):
        response = client.post(
            "/api/plants/simulate",
            json={
                "plant_codes": ["GRASS_DEEP", "SHRUB", "TREE"],
                "coverage_pct": 80.0,
                "season": "summer"
            }
        )
        self.assertEqual(response.status_code, 200)
        data = response.json()
        self.assertGreater(data["combined_bonus_pct"], 0)
        self.assertEqual(len(data["individual_effects"]), 3)
        self.assertIn("overall_cohesion_increase_kpa", data)


class TestVRRammedEarthAPI(unittest.TestCase):
    def test_vr_presets(self):
        response = client.get("/api/virtual/presets")
        self.assertEqual(response.status_code, 200)
        data = response.json()
        self.assertIn("dynasty_presets", data)
        self.assertIn("base_materials", data)
        self.assertIn("tamping_presets", data)
        self.assertIn("QIN", data["dynasty_presets"])

    def test_vr_evaluate_standard(self):
        response = client.post(
            "/api/virtual/evaluate",
            json={
                "mix": {
                    "soil_pct": 65,
                    "clay_pct": 20,
                    "sand_pct": 5,
                    "lime_pct": 3,
                    "rice_paste_pct": 2,
                    "straw_pct": 1,
                    "water_pct": 16
                },
                "tamping_preset": "heavy",
                "wall_height_m": 2.5
            }
        )
        self.assertEqual(response.status_code, 200)
        data = response.json()
        self.assertIn("quality_score", data)
        self.assertGreater(data["quality_score"], 0)
        self.assertIn("quality_rating", data)
        self.assertIn("erosion_rate_mm_per_year", data)

    def test_vr_evaluate_qin_preset(self):
        response = client.get("/api/virtual/presets")
        presets = response.json()
        qin_mix = presets["dynasty_presets"]["QIN"]["mix"]

        response2 = client.post(
            "/api/virtual/evaluate",
            json={
                "mix": qin_mix,
                "tamping_preset": "heavy"
            }
        )
        data = response2.json()
        self.assertEqual(data["dynasty_match"], "QIN")
        self.assertGreater(data["dynasty_match_score"], 0.9)


class TestNewModuleEndpointsExist(unittest.TestCase):
    def test_new_cross_era_endpoint(self):
        response = client.post(
            "/api/cross-era/compare",
            json={"include_dynasties": ["QIN"], "include_modern": []}
        )
        self.assertEqual(response.status_code, 200)

    def test_new_route_under_new_prefix(self):
        response1 = client.get("/api/dynasty/list")
        self.assertEqual(response1.status_code, 200)
        response2 = client.get("/api/plants/species")
        self.assertEqual(response2.status_code, 200)
        response3 = client.get("/api/virtual/presets")
        self.assertEqual(response3.status_code, 200)


if __name__ == "__main__":
    print("=" * 75)
    print("New module API tests")
    print("=" * 75)
    unittest.main(verbosity=2)
