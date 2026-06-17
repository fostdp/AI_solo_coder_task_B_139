import sys
sys.path.insert(0, '.')

import os
os.environ.pop('DATABASE_URL', None)
os.environ.pop('TIMESCALEDB_URL', None)

from backend.config import settings
settings.DATABASE_URL = 'sqlite+aiosqlite:///./test.db'
settings.TIMESCALEDB_URL = 'sqlite:///./test_sync.db'

for mod in list(sys.modules.keys()):
    if 'backend.database' in mod or 'backend.models.orm' in mod:
        del sys.modules[mod]

import numpy as np
from backend.services.dynasty_comparison import dynasty_comparison_service
from backend.services.plant_root_simulation import plant_root_service
from backend.services.virtual_experience import virtual_experience_service
from backend.models.new_schemas import (
    DynastyComparisonRequest,
    CrossEraComparisonRequest,
    PlantRootSimulationRequest,
    VirtualExperienceRequest,
    MaterialMix
)

print("=" * 75)
print("🧪 新增Feature单元测试用例 - 服务层验证")
print("=" * 75)
print()

passed = 0
failed = 0
tests = []

def run_test(name, test_func):
    global passed, failed
    try:
        test_func()
        passed += 1
        tests.append((name, "PASS", ""))
        print(f"✅ {name} -> PASS")
    except AssertionError as e:
        failed += 1
        tests.append((name, "FAIL", str(e)))
        print(f"❌ {name} -> FAIL: {e}")
    except Exception as e:
        failed += 1
        tests.append((name, "ERROR", str(e)))
        print(f"💥 {name} -> ERROR: {e}")

# ======================================================================
# Feature 1: 朝代工艺对比 - 验证风蚀速率
# ======================================================================
print("\n" + "=" * 75)
print("🏺 Feature 1: 朝代工艺对比 - 风蚀速率验证")
print("=" * 75)

# --- 正常场景 ---
def test_dynasty_normal():
    req = DynastyComparisonRequest(
        dynasty_codes=["QIN", "HAN", "MING"],
        wind_speed=8.0,
        soil_moisture=5.0,
        duration_hours=24
    )
    res = dynasty_comparison_service.compare_dynasties(
        req.dynasty_codes, req.wind_speed, req.soil_moisture,
        req.duration_hours, req.climate_scenario
    )
    assert res is not None, "结果不能为空"
    assert len(res["results"]) == 3, "应返回3个朝代结果"
    rates = [r["erosion_rate_mm_per_year"] for r in res["results"]]
    assert all(0.001 < r < 5000 for r in rates), f"侵蚀率应在合理范围内: {rates}"
    ranks = [r["rank"] for r in res["results"]]
    assert sorted(ranks) == [1, 2, 3], "排名应连续不重复"
    scores = [r["overall_score"] for r in res["results"]]
    assert scores == sorted(scores, reverse=True), "应按评分降序排列"
    print(f"   侵蚀率: QIN={rates[0]:.3f}, HAN={rates[1]:.3f}, MING={rates[2]:.3f} mm/年")
    print(f"   排名: {[r['dynasty_code'] for r in res['results']]}")

run_test("1.1 正常场景-三代工艺对比", test_dynasty_normal)

def test_dynasty_climate_scenario():
    req = DynastyComparisonRequest(
        dynasty_codes=["QIN", "HAN"],
        wind_speed=8.0,
        soil_moisture=5.0,
        duration_hours=24,
        climate_scenario="arid"
    )
    res = dynasty_comparison_service.compare_dynasties(
        req.dynasty_codes, req.wind_speed, req.soil_moisture,
        req.duration_hours, req.climate_scenario
    )
    assert res["climate_scenario"]["description"] == "干旱区（西北）"
    rates_arid = [r["erosion_rate_mm_per_year"] for r in res["results"]]
    req2 = DynastyComparisonRequest(
        dynasty_codes=["QIN", "HAN"],
        wind_speed=8.0,
        soil_moisture=5.0,
        duration_hours=24,
        climate_scenario="humid"
    )
    res2 = dynasty_comparison_service.compare_dynasties(
        req2.dynasty_codes, req2.wind_speed, req2.soil_moisture,
        req2.duration_hours, req2.climate_scenario
    )
    rates_humid = [r["erosion_rate_mm_per_year"] for r in res2["results"]]
    assert any(a != b for a, b in zip(rates_arid, rates_humid)), "不同气候应产生不同侵蚀率"
    print(f"   干旱区 Qin: {rates_arid[0]:.4f}, 湿润区 Qin: {rates_humid[0]:.4f}")

run_test("1.2 正常场景-气候场景差异", test_dynasty_climate_scenario)

# --- 边界场景 ---
def test_dynasty_boundary_wind_low():
    req = DynastyComparisonRequest(
        dynasty_codes=["QIN"],
        wind_speed=0.1,
        soil_moisture=5.0,
        duration_hours=24
    )
    res = dynasty_comparison_service.compare_dynasties(
        req.dynasty_codes, req.wind_speed, req.soil_moisture,
        req.duration_hours, req.climate_scenario
    )
    rate = res["results"][0]["erosion_rate_mm_per_year"]
    assert 0.0 < rate < 0.5, f"极低风速下侵蚀率应很低: {rate}"
    print(f"   风速0.1m/s -> 侵蚀率={rate:.4f} mm/年")

run_test("1.3 边界场景-极低风速", test_dynasty_boundary_wind_low)

def test_dynasty_boundary_wind_high():
    req = DynastyComparisonRequest(
        dynasty_codes=["QIN"],
        wind_speed=30.0,
        soil_moisture=5.0,
        duration_hours=24
    )
    res = dynasty_comparison_service.compare_dynasties(
        req.dynasty_codes, req.wind_speed, req.soil_moisture,
        req.duration_hours, req.climate_scenario
    )
    rate = res["results"][0]["erosion_rate_mm_per_year"]
    assert rate > 0.5, f"极高风速下侵蚀率应较高: {rate}"
    print(f"   风速30m/s -> 侵蚀率={rate:.4f} mm/年")

run_test("1.4 边界场景-极高风速", test_dynasty_boundary_wind_high)

def test_dynasty_boundary_single_dynasty():
    req = DynastyComparisonRequest(
        dynasty_codes=["QIN"],
        wind_speed=8.0,
        soil_moisture=5.0
    )
    res = dynasty_comparison_service.compare_dynasties(
        req.dynasty_codes, req.wind_speed, req.soil_moisture,
        req.duration_hours, req.climate_scenario
    )
    assert len(res["results"]) == 1
    assert res["results"][0]["rank"] == 1
    print(f"   单朝代测试: {res['results'][0]['name']} -> 评分={res['results'][0]['overall_score']:.3f}")

run_test("1.5 边界场景-单朝代", test_dynasty_boundary_single_dynasty)

def test_dynasty_boundary_wind_zero():
    req = DynastyComparisonRequest(
        dynasty_codes=["QIN"],
        wind_speed=0.0,
        soil_moisture=5.0
    )
    res = dynasty_comparison_service.compare_dynasties(
        req.dynasty_codes, req.wind_speed, req.soil_moisture,
        req.duration_hours, req.climate_scenario
    )
    rate = res["results"][0]["erosion_rate_mm_per_year"]
    assert rate >= 0, f"零风速下侵蚀率应为非负: {rate}"
    print(f"   零风速 -> 侵蚀率={rate:.4f} mm/年")

run_test("1.6 边界场景-零风速", test_dynasty_boundary_wind_zero)

# --- 异常场景 ---
def test_dynasty_abnormal_invalid_code():
    req = DynastyComparisonRequest(
        dynasty_codes=["INVALID_DYNASTY"],
        wind_speed=8.0,
        soil_moisture=5.0
    )
    res = dynasty_comparison_service.compare_dynasties(
        req.dynasty_codes, req.wind_speed, req.soil_moisture,
        req.duration_hours, req.climate_scenario
    )
    assert len(res["results"]) == 0, f"无效朝代应返回空列表，实际={len(res['results'])}"
    print(f"   无效朝代 -> 返回{len(res['results'])}个结果 (正确)")

run_test("1.7 异常场景-无效朝代代码", test_dynasty_abnormal_invalid_code)

def test_dynasty_abnormal_empty_list():
    req = DynastyComparisonRequest(
        dynasty_codes=[],
        wind_speed=8.0,
        soil_moisture=5.0
    )
    res = dynasty_comparison_service.compare_dynasties(
        req.dynasty_codes, req.wind_speed, req.soil_moisture,
        req.duration_hours, req.climate_scenario
    )
    assert len(res["results"]) == 0, "空列表应返回空"
    print(f"   空列表 -> 返回{len(res['results'])}个结果 (正确)")

run_test("1.8 异常场景-空朝代列表", test_dynasty_abnormal_empty_list)

def test_dynasty_abnormal_invalid_climate():
    req = DynastyComparisonRequest(
        dynasty_codes=["QIN"],
        wind_speed=8.0,
        soil_moisture=5.0,
        climate_scenario="INVALID_CLIMATE"
    )
    res = dynasty_comparison_service.compare_dynasties(
        req.dynasty_codes, req.wind_speed, req.soil_moisture,
        req.duration_hours, req.climate_scenario
    )
    assert len(res["results"]) == 1, "无效气候应使用默认值，仍返回结果"
    assert res["climate_scenario"]["name"] == "default", "应返回默认气候"
    print(f"   无效气候 -> 使用默认气候 (正确)")

run_test("1.9 异常场景-无效气候场景", test_dynasty_abnormal_invalid_climate)

# ======================================================================
# Feature 2: 跨时代工程对比 - 验证力学性能
# ======================================================================
print("\n" + "=" * 75)
print("⚒️  Feature 2: 跨时代工程对比 - 力学性能验证")
print("=" * 75)

# --- 正常场景 ---
def test_crossera_normal():
    req = CrossEraComparisonRequest(
        include_dynasties=["QIN", "HAN", "MING"],
        include_modern=["GEOSYNTHETIC", "FIBER", "CEMENT"],
        wind_speed=8.0,
        soil_moisture=5.0
    )
    res = dynasty_comparison_service.compare_cross_era(
        req.include_dynasties, req.include_modern,
        req.wind_speed, req.soil_moisture
    )
    assert len(res["items"]) == 6, f"应返回6个方案，实际={len(res['items'])}"
    codes = [it["code"] for it in res["items"]]
    assert "QIN" in codes and "GEOSYNTHETIC" in codes
    eras = [it["era"] for it in res["items"]]
    assert "ancient" in eras and "modern" in eras
    topsis_scores = [it["topsis_score"] for it in res["items"]]
    assert all(0.0 <= s <= 1.0 for s in topsis_scores if s is not None), "TOPSIS评分应在0-1之间"
    hardness_values = [it["hardness_mpa"] for it in res["items"]]
    print(f"   力学性能范围: 硬度={min(hardness_values):.2f}~{max(hardness_values):.2f} MPa")
    print(f"   TOPSIS排名: {[it['code'] for it in res['items'][:3]]}...")

run_test("2.1 正常场景-六方案对比", test_crossera_normal)

def test_crossera_ancient_only():
    req = CrossEraComparisonRequest(
        include_dynasties=["QIN", "HAN", "MING"],
        include_modern=[],
        wind_speed=8.0,
        soil_moisture=5.0
    )
    res = dynasty_comparison_service.compare_cross_era(
        req.include_dynasties, req.include_modern,
        req.wind_speed, req.soil_moisture
    )
    assert len(res["items"]) == 3
    assert all(it["era"] == "ancient" for it in res["items"])
    print(f"   仅古代方案 -> 返回{len(res['items'])}个结果")

run_test("2.2 正常场景-仅古代方案", test_crossera_ancient_only)

def test_crossera_modern_only():
    req = CrossEraComparisonRequest(
        include_dynasties=[],
        include_modern=["GEOSYNTHETIC", "FIBER", "CEMENT"],
        wind_speed=8.0,
        soil_moisture=5.0
    )
    res = dynasty_comparison_service.compare_cross_era(
        req.include_dynasties, req.include_modern,
        req.wind_speed, req.soil_moisture
    )
    assert len(res["items"]) == 3
    assert all(it["era"] == "modern" for it in res["items"])
    print(f"   仅现代方案 -> 返回{len(res['items'])}个结果")

run_test("2.3 正常场景-仅现代方案", test_crossera_modern_only)

# --- 边界场景 ---
def test_crossera_boundary_hardness():
    req = CrossEraComparisonRequest(
        include_dynasties=["QIN"],
        include_modern=["CEMENT"],
        wind_speed=8.0,
        soil_moisture=5.0
    )
    res = dynasty_comparison_service.compare_cross_era(
        req.include_dynasties, req.include_modern,
        req.wind_speed, req.soil_moisture
    )
    cement = [it for it in res["items"] if it["code"] == "CEMENT"][0]
    qin = [it for it in res["items"] if it["code"] == "QIN"][0]
    assert cement["hardness_mpa"] > qin["hardness_mpa"], f"水泥土硬度应高于秦代夯土: 水泥={cement['hardness_mpa']:.2f}, 秦={qin['hardness_mpa']:.2f}"
    assert cement["cohesion_kpa"] > qin["cohesion_kpa"], "水泥土粘结力应更高"
    print(f"   水泥土: 硬度={cement['hardness_mpa']:.2f} MPa, 粘结力={cement['cohesion_kpa']:.1f} kPa")
    print(f"   秦代夯土: 硬度={qin['hardness_mpa']:.2f} MPa, 粘结力={qin['cohesion_kpa']:.1f} kPa")

run_test("2.4 边界场景-现代vs古代力学性能对比", test_crossera_boundary_hardness)

def test_crossera_boundary_cultural_authenticity():
    req = CrossEraComparisonRequest(
        include_dynasties=["QIN"],
        include_modern=["GEOSYNTHETIC"],
        wind_speed=8.0,
        soil_moisture=5.0
    )
    res = dynasty_comparison_service.compare_cross_era(
        req.include_dynasties, req.include_modern,
        req.wind_speed, req.soil_moisture
    )
    ancient = [it for it in res["items"] if it["era"] == "ancient"][0]
    modern = [it for it in res["items"] if it["era"] == "modern"][0]
    assert ancient["cultural_authenticity"] > modern["cultural_authenticity"], "古代方案文化真实性应更高"
    assert ancient["reversibility"] > modern["reversibility"], "古代方案可逆性应更高"
    assert modern["environmental_impact"] > ancient["environmental_impact"], "现代方案环境影响应更大"
    print(f"   文化真实性: 古代={ancient['cultural_authenticity']}, 现代={modern['cultural_authenticity']}")
    print(f"   可逆性: 古代={ancient['reversibility']}, 现代={modern['reversibility']}")

run_test("2.5 边界场景-文化/可逆/环境指标验证", test_crossera_boundary_cultural_authenticity)

def test_crossera_boundary_single_each():
    req = CrossEraComparisonRequest(
        include_dynasties=["QIN"],
        include_modern=["FIBER"],
        wind_speed=8.0,
        soil_moisture=5.0
    )
    res = dynasty_comparison_service.compare_cross_era(
        req.include_dynasties, req.include_modern,
        req.wind_speed, req.soil_moisture
    )
    assert len(res["items"]) == 2
    assert len(res["ranking"]) == 2
    print(f"   1古1今对比 -> 排名1: {res['ranking'][0]['code']}, 评分={res['ranking'][0]['topsis_score']:.3f}")

run_test("2.6 边界场景-单个古今对比", test_crossera_boundary_single_each)

# --- 异常场景 ---
def test_crossera_abnormal_all_empty():
    req = CrossEraComparisonRequest(
        include_dynasties=[],
        include_modern=[],
        wind_speed=8.0,
        soil_moisture=5.0
    )
    res = dynasty_comparison_service.compare_cross_era(
        req.include_dynasties, req.include_modern,
        req.wind_speed, req.soil_moisture
    )
    assert len(res["items"]) == 0, "全空应返回空列表"
    print(f"   全空列表 -> 返回{len(res['items'])}个结果 (正确)")

run_test("2.7 异常场景-双空列表", test_crossera_abnormal_all_empty)

def test_crossera_abnormal_invalid_modern():
    req = CrossEraComparisonRequest(
        include_dynasties=["QIN"],
        include_modern=["INVALID_MATERIAL"],
        wind_speed=8.0,
        soil_moisture=5.0
    )
    res = dynasty_comparison_service.compare_cross_era(
        req.include_dynasties, req.include_modern,
        req.wind_speed, req.soil_moisture
    )
    codes = [it["code"] for it in res["items"]]
    assert "INVALID_MATERIAL" not in codes
    assert "QIN" in codes
    print(f"   无效现代材料 -> 仅返回有效项 (正确)")

run_test("2.8 异常场景-无效现代材料", test_crossera_abnormal_invalid_modern)

def test_crossera_abnormal_mixed_valid_invalid():
    req = CrossEraComparisonRequest(
        include_dynasties=["QIN", "INVALID"],
        include_modern=["FIBER", "BAD_CODE"],
        wind_speed=8.0,
        soil_moisture=5.0
    )
    res = dynasty_comparison_service.compare_cross_era(
        req.include_dynasties, req.include_modern,
        req.wind_speed, req.soil_moisture
    )
    assert len(res["items"]) == 2, f"应过滤无效项，返回2个，实际={len(res['items'])}"
    codes = [it["code"] for it in res["items"]]
    assert "QIN" in codes and "FIBER" in codes
    print(f"   混合有效/无效 -> 过滤后返回{len(res['items'])}个 (正确)")

run_test("2.9 异常场景-混合有效无效代码", test_crossera_abnormal_mixed_valid_invalid)

# ======================================================================
# Feature 3: 植物根系防护 - 验证风速衰减
# ======================================================================
print("\n" + "=" * 75)
print("🌱  Feature 3: 植物根系防护 - 风速衰减验证")
print("=" * 75)

# --- 正常场景 ---
def test_plant_normal():
    req = PlantRootSimulationRequest(
        plant_codes=["GRASS_DEEP", "SHRUB"],
        coverage_pct=70.0,
        wall_height_m=2.5,
        wind_speed=8.0,
        soil_moisture=5.0,
        season="summer"
    )
    res = plant_root_service.simulate_plant_protection(
        req.plant_codes, req.coverage_pct, req.wall_height_m,
        req.wind_speed, req.soil_moisture, req.season
    )
    assert res is not None
    assert res["protected_erosion_rate"] < res["baseline_erosion_rate"], "防护后侵蚀率应降低"
    assert res["total_reduction_pct"] > 0, "总降低率应大于0"
    assert res["total_reduction_pct"] < 95, "总降低率不应超过95%"
    wind_reductions = [e["wind_speed_reduction_pct"] for e in res["individual_effects"]]
    assert all(r > 0 for r in wind_reductions), "各植物风速降低率应大于0"
    print(f"   基准侵蚀率: {res['baseline_erosion_rate']:.4f} mm/年")
    print(f"   防护后: {res['protected_erosion_rate']:.4f} mm/年")
    print(f"   总降低率: {res['total_reduction_pct']:.1f}%")
    print(f"   风速降低: {wind_reductions}")

run_test("3.1 正常场景-灌草组合防护", test_plant_normal)

def test_plant_get_species():
    plants = plant_root_service.get_available_plants()
    assert len(plants) >= 4, f"应至少4种植物，实际={len(plants)}"
    codes = [p["code"] for p in plants]
    for expected in ["GRASS_SHORT", "GRASS_DEEP", "SHRUB", "TREE"]:
        assert expected in codes, f"应包含{expected}"
    print(f"   植物种类: {[p['name_zh'] for p in plants]}")

run_test("3.2 正常场景-获取植物列表", test_plant_get_species)

def test_plant_combination_bonus():
    req_multi = PlantRootSimulationRequest(
        plant_codes=["GRASS_DEEP", "SHRUB", "TREE"],
        coverage_pct=70.0,
        wall_height_m=2.5,
        wind_speed=8.0,
        soil_moisture=5.0,
        season="summer"
    )
    res_multi = plant_root_service.simulate_plant_protection(
        req_multi.plant_codes, req_multi.coverage_pct, req_multi.wall_height_m,
        req_multi.wind_speed, req_multi.soil_moisture, req_multi.season
    )
    req_single = PlantRootSimulationRequest(
        plant_codes=["TREE"],
        coverage_pct=70.0,
        wall_height_m=2.5,
        wind_speed=8.0,
        soil_moisture=5.0,
        season="summer"
    )
    res_single = plant_root_service.simulate_plant_protection(
        req_single.plant_codes, req_single.coverage_pct, req_single.wall_height_m,
        req_single.wind_speed, req_single.soil_moisture, req_single.season
    )
    assert res_multi["combined_bonus_pct"] > 0, f"多种植物应有组合加成，实际={res_multi['combined_bonus_pct']}"
    print(f"   组合加成: +{res_multi['combined_bonus_pct']}%")
    print(f"   仅乔木降低率: {res_single['total_reduction_pct']:.1f}%, 三层复合: {res_multi['total_reduction_pct']:.1f}%")

run_test("3.3 正常场景-组合加成验证", test_plant_combination_bonus)

# --- 边界场景 ---
def test_plant_boundary_zero_coverage():
    req = PlantRootSimulationRequest(
        plant_codes=["GRASS_DEEP", "SHRUB"],
        coverage_pct=0.0,
        wall_height_m=2.5,
        wind_speed=8.0,
        soil_moisture=5.0,
        season="summer"
    )
    res = plant_root_service.simulate_plant_protection(
        req.plant_codes, req.coverage_pct, req.wall_height_m,
        req.wind_speed, req.soil_moisture, req.season
    )
    assert abs(res["total_reduction_pct"]) < 0.01, f"零覆盖率下防护效果应为0，实际={res['total_reduction_pct']}"
    assert abs(res["protected_erosion_rate"] - res["baseline_erosion_rate"]) < 0.001
    print(f"   覆盖率0% -> 侵蚀降低={res['total_reduction_pct']:.2f}% (正确)")

run_test("3.4 边界场景-零覆盖率", test_plant_boundary_zero_coverage)

def test_plant_boundary_full_coverage():
    req = PlantRootSimulationRequest(
        plant_codes=["TREE"],
        coverage_pct=95.0,
        wall_height_m=2.5,
        wind_speed=8.0,
        soil_moisture=5.0,
        season="summer"
    )
    res = plant_root_service.simulate_plant_protection(
        req.plant_codes, req.coverage_pct, req.wall_height_m,
        req.wind_speed, req.soil_moisture, req.season
    )
    assert res["total_reduction_pct"] > 30, f"高覆盖率下应有显著防护效果: {res['total_reduction_pct']}"
    print(f"   覆盖率95% -> 侵蚀降低={res['total_reduction_pct']:.1f}%")

run_test("3.5 边界场景-极高覆盖率", test_plant_boundary_full_coverage)

def test_plant_boundary_seasonal_effect():
    req_summer = PlantRootSimulationRequest(
        plant_codes=["GRASS_DEEP"],
        coverage_pct=70.0,
        wall_height_m=2.5,
        wind_speed=8.0,
        soil_moisture=5.0,
        season="summer"
    )
    res_summer = plant_root_service.simulate_plant_protection(
        req_summer.plant_codes, req_summer.coverage_pct, req_summer.wall_height_m,
        req_summer.wind_speed, req_summer.soil_moisture, req_summer.season
    )
    req_winter = PlantRootSimulationRequest(
        plant_codes=["GRASS_DEEP"],
        coverage_pct=70.0,
        wall_height_m=2.5,
        wind_speed=8.0,
        soil_moisture=5.0,
        season="winter"
    )
    res_winter = plant_root_service.simulate_plant_protection(
        req_winter.plant_codes, req_winter.coverage_pct, req_winter.wall_height_m,
        req_winter.wind_speed, req_winter.soil_moisture, req_winter.season
    )
    assert res_summer["total_reduction_pct"] > res_winter["total_reduction_pct"], "夏季防护效果应优于冬季"
    print(f"   夏季降低率: {res_summer['total_reduction_pct']:.1f}%")
    print(f"   冬季降低率: {res_winter['total_reduction_pct']:.1f}%")

run_test("3.6 边界场景-季节衰减验证", test_plant_boundary_seasonal_effect)

def test_plant_boundary_tree_max_effect():
    req = PlantRootSimulationRequest(
        plant_codes=["TREE"],
        coverage_pct=80.0,
        wall_height_m=2.5,
        wind_speed=12.0,
        soil_moisture=5.0,
        season="summer"
    )
    res = plant_root_service.simulate_plant_protection(
        req.plant_codes, req.coverage_pct, req.wall_height_m,
        req.wind_speed, req.soil_moisture, req.season
    )
    effects = res["individual_effects"]
    assert len(effects) == 1
    assert effects[0]["wind_speed_reduction_pct"] > 30, f"乔木应有显著风速衰减: {effects[0]['wind_speed_reduction_pct']}%"
    print(f"   乔木风速降低: {effects[0]['wind_speed_reduction_pct']:.1f}%")

run_test("3.7 边界场景-乔木风速衰减验证", test_plant_boundary_tree_max_effect)

# --- 异常场景 ---
def test_plant_abnormal_invalid_code():
    req = PlantRootSimulationRequest(
        plant_codes=["INVALID_PLANT"],
        coverage_pct=70.0,
        wall_height_m=2.5,
        wind_speed=8.0,
        soil_moisture=5.0,
        season="summer"
    )
    res = plant_root_service.simulate_plant_protection(
        req.plant_codes, req.coverage_pct, req.wall_height_m,
        req.wind_speed, req.soil_moisture, req.season
    )
    assert len(res["individual_effects"]) == 0
    assert res["total_reduction_pct"] == 0.0
    print(f"   无效植物 -> 无防护效果 (正确)")

run_test("3.8 异常场景-无效植物代码", test_plant_abnormal_invalid_code)

def test_plant_abnormal_empty_plants():
    req = PlantRootSimulationRequest(
        plant_codes=[],
        coverage_pct=70.0,
        wall_height_m=2.5,
        wind_speed=8.0,
        soil_moisture=5.0,
        season="summer"
    )
    res = plant_root_service.simulate_plant_protection(
        req.plant_codes, req.coverage_pct, req.wall_height_m,
        req.wind_speed, req.soil_moisture, req.season
    )
    assert len(res["individual_effects"]) == 0
    assert res["total_reduction_pct"] == 0.0
    assert res["baseline_erosion_rate"] == res["protected_erosion_rate"]
    print(f"   空植物列表 -> 无防护效果 (正确)")

run_test("3.9 异常场景-空植物列表", test_plant_abnormal_empty_plants)

def test_plant_abnormal_negative_coverage():
    req = PlantRootSimulationRequest(
        plant_codes=["GRASS_DEEP"],
        coverage_pct=-5.0,
        wall_height_m=2.5,
        wind_speed=8.0,
        soil_moisture=5.0,
        season="summer"
    )
    res = plant_root_service.simulate_plant_protection(
        req.plant_codes, req.coverage_pct, req.wall_height_m,
        req.wind_speed, req.soil_moisture, req.season
    )
    assert res["total_reduction_pct"] >= 0, "负覆盖率不应产生负防护效果"
    print(f"   负覆盖率 -> 防护率={res['total_reduction_pct']:.2f}% (安全)")

run_test("3.10 异常场景-负覆盖率", test_plant_abnormal_negative_coverage)

def test_plant_abnormal_invalid_season():
    req = PlantRootSimulationRequest(
        plant_codes=["GRASS_DEEP"],
        coverage_pct=70.0,
        wall_height_m=2.5,
        wind_speed=8.0,
        soil_moisture=5.0,
        season="invalid_season"
    )
    res = plant_root_service.simulate_plant_protection(
        req.plant_codes, req.coverage_pct, req.wall_height_m,
        req.wind_speed, req.soil_moisture, req.season
    )
    assert res is not None, "无效季节应仍有默认处理"
    print(f"   无效季节 -> 正常返回 (正确)")

run_test("3.11 异常场景-无效季节", test_plant_abnormal_invalid_season)

# ======================================================================
# Feature 4: 虚拟夯土体验 - 测试交互教育性
# ======================================================================
print("\n" + "=" * 75)
print("👐  Feature 4: 虚拟夯土体验 - 交互教育性测试")
print("=" * 75)

# --- 正常场景 ---
def test_virtual_normal_mix():
    mix = MaterialMix(
        soil_pct=65, clay_pct=15, sand_pct=10,
        lime_pct=3, rice_paste_pct=2, straw_pct=1, water_pct=16
    )
    req = VirtualExperienceRequest(
        mix=mix,
        tamping_preset="heavy",
        wall_height_m=2.5,
        wind_speed=8.0
    )
    mix_dict = {
        "soil_pct": req.mix.soil_pct, "clay_pct": req.mix.clay_pct,
        "sand_pct": req.mix.sand_pct, "lime_pct": req.mix.lime_pct,
        "rice_paste_pct": req.mix.rice_paste_pct, "straw_pct": req.mix.straw_pct,
        "water_pct": req.mix.water_pct
    }
    res = virtual_experience_service.evaluate_mix(
        mix_dict, req.tamping_preset, req.wall_height_m, req.wind_speed
    )
    assert res is not None
    assert 0.0 <= res["quality_score"] <= 1.0, f"质量评分应在0-1之间: {res['quality_score']}"
    assert res["quality_rating"] in ["优", "良", "中", "差", "劣"]
    assert res["compaction_ratio"] > 0.6, f"压实度应合理: {res['compaction_ratio']}"
    assert res["erosion_rate_mm_per_year"] > 0
    assert res["hardness_mpa"] > 0
    assert len(res["suggestions"]) > 0, "应有改进建议"
    assert res["dynasty_match"] in ["QIN", "HAN", "MING"]
    assert 0.0 <= res["dynasty_match_score"] <= 1.0
    print(f"   质量评分: {res['quality_score']:.3f} -> {res['quality_rating']}")
    print(f"   压实度: {res['compaction_ratio']:.2%}")
    print(f"   侵蚀率: {res['erosion_rate_mm_per_year']:.3f} mm/年")
    print(f"   匹配朝代: {res['dynasty_match']} (相似度{res['dynasty_match_score']:.0%})")
    print(f"   建议数: {len(res['suggestions'])}条")

run_test("4.1 正常场景-标准配比评估", test_virtual_normal_mix)

def test_virtual_get_presets():
    presets = virtual_experience_service.get_material_presets()
    assert "base_materials" in presets
    assert "tamping_presets" in presets
    assert "soil" in presets["base_materials"]
    assert "heavy" in presets["tamping_presets"]
    dynasties = virtual_experience_service.get_dynasty_presets()
    assert len(dynasties) == 3
    for k in ["QIN", "HAN", "MING"]:
        assert k in dynasties
        assert "mix" in dynasties[k]
    print(f"   材料预设: {list(presets['base_materials'].keys())}")
    print(f"   夯打预设: {list(presets['tamping_presets'].keys())}")

run_test("4.2 正常场景-获取预设", test_virtual_get_presets)

def test_virtual_dynasty_presets():
    dynasties = virtual_experience_service.get_dynasty_presets()
    for code in ["QIN", "HAN", "MING"]:
        mix = dynasties[code]["mix"]
        mix_dict = {
            "soil_pct": mix["soil_pct"], "clay_pct": mix["clay_pct"],
            "sand_pct": mix["sand_pct"], "lime_pct": mix["lime_pct"],
            "rice_paste_pct": mix["rice_paste_pct"], "straw_pct": mix["straw_pct"],
            "water_pct": mix["water_pct"]
        }
        res = virtual_experience_service.evaluate_mix(
            mix_dict, dynasties[code]["tamping"], 2.5, 8.0
        )
        assert res["dynasty_match"] == code, f"{code}预设应匹配自身，实际={res['dynasty_match']}"
        assert res["dynasty_match_score"] > 0.8, f"匹配度应>80%: {res['dynasty_match_score']}"
        print(f"   {code}预设 -> 匹配度={res['dynasty_match_score']:.0%}, 评分={res['quality_score']:.2f}")

run_test("4.3 正常场景-朝代预设自匹配", test_virtual_dynasty_presets)

# --- 边界场景 ---
def test_virtual_boundary_optimal_water():
    mix_dict = {
        "soil_pct": 65, "clay_pct": 15, "sand_pct": 10,
        "lime_pct": 3, "rice_paste_pct": 2, "straw_pct": 1, "water_pct": 16
    }
    res_optimal = virtual_experience_service.evaluate_mix(mix_dict, "heavy", 2.5, 8.0)
    mix_dry = {**mix_dict, "water_pct": 8}
    res_dry = virtual_experience_service.evaluate_mix(mix_dry, "heavy", 2.5, 8.0)
    mix_wet = {**mix_dict, "water_pct": 22}
    res_wet = virtual_experience_service.evaluate_mix(mix_wet, "heavy", 2.5, 8.0)
    assert res_optimal["compaction_ratio"] >= res_dry["compaction_ratio"], "最优含水量压实度应最高"
    assert res_optimal["compaction_ratio"] >= res_wet["compaction_ratio"], "最优含水量压实度应最高"
    print(f"   含水量8%  -> 压实度={res_dry['compaction_ratio']:.3f}")
    print(f"   含水量16% -> 压实度={res_optimal['compaction_ratio']:.3f} (最优)")
    print(f"   含水量22% -> 压实度={res_wet['compaction_ratio']:.3f}")

run_test("4.4 边界场景-最优含水量验证", test_virtual_boundary_optimal_water)

def test_virtual_boundary_tamping_effect():
    mix_dict = {
        "soil_pct": 65, "clay_pct": 15, "sand_pct": 10,
        "lime_pct": 3, "rice_paste_pct": 2, "straw_pct": 1, "water_pct": 16
    }
    results = {}
    for tamping in ["light", "medium", "heavy", "extreme"]:
        res = virtual_experience_service.evaluate_mix(mix_dict, tamping, 2.5, 8.0)
        results[tamping] = res["compaction_ratio"]
    assert results["extreme"] > results["heavy"] > results["medium"] > results["light"], "夯打力度与压实度应正相关"
    print(f"   压实度排序: 极重夯({results['extreme']:.3f}) > 重夯({results['heavy']:.3f}) > 中夯({results['medium']:.3f}) > 轻夯({results['light']:.3f})")

run_test("4.5 边界场景-夯打力度梯度验证", test_virtual_boundary_tamping_effect)

def test_virtual_boundary_lime_reinforcement():
    base = {"soil_pct": 70, "clay_pct": 18, "sand_pct": 10,
            "lime_pct": 0, "rice_paste_pct": 0, "straw_pct": 2, "water_pct": 16}
    res_no_lime = virtual_experience_service.evaluate_mix(base, "heavy", 2.5, 8.0)
    with_lime = {**base, "lime_pct": 12, "soil_pct": 58}
    res_with_lime = virtual_experience_service.evaluate_mix(with_lime, "heavy", 2.5, 8.0)
    assert res_with_lime["moisture_resistance"] > res_no_lime["moisture_resistance"], "加石灰抗水性应提升"
    assert res_with_lime["hardness_mpa"] > res_no_lime["hardness_mpa"], "加石灰硬度应提升"
    assert res_with_lime["erosion_rate_mm_per_year"] < res_no_lime["erosion_rate_mm_per_year"], "加石灰侵蚀率应降低"
    print(f"   无石灰 -> 抗水性={res_no_lime['moisture_resistance']:.2f}, 侵蚀率={res_no_lime['erosion_rate_mm_per_year']:.3f}")
    print(f"   12%石灰 -> 抗水性={res_with_lime['moisture_resistance']:.2f}, 侵蚀率={res_with_lime['erosion_rate_mm_per_year']:.3f}")

run_test("4.6 边界场景-石灰强化效果验证", test_virtual_boundary_lime_reinforcement)

def test_virtual_boundary_straw_crack_resistance():
    base = {"soil_pct": 66, "clay_pct": 15, "sand_pct": 10,
            "lime_pct": 3, "rice_paste_pct": 2, "straw_pct": 0, "water_pct": 16}
    res_no_straw = virtual_experience_service.evaluate_mix(base, "heavy", 2.5, 8.0)
    with_straw = {**base, "straw_pct": 5, "soil_pct": 61}
    res_with_straw = virtual_experience_service.evaluate_mix(with_straw, "heavy", 2.5, 8.0)
    assert res_with_straw["crack_resistance"] > res_no_straw["crack_resistance"], "加麦草抗裂性应提升"
    print(f"   无麦草 -> 抗裂性={res_no_straw['crack_resistance']:.2f}")
    print(f"   5%麦草 -> 抗裂性={res_with_straw['crack_resistance']:.2f}")

run_test("4.7 边界场景-麦草抗裂验证", test_virtual_boundary_straw_crack_resistance)

def test_virtual_boundary_extreme_quality():
    excellent_mix = {"soil_pct": 60, "clay_pct": 20, "sand_pct": 8,
                     "lime_pct": 8, "rice_paste_pct": 3, "straw_pct": 1, "water_pct": 16}
    res = virtual_experience_service.evaluate_mix(excellent_mix, "extreme", 2.5, 8.0)
    assert res["quality_score"] >= 0.50, f"优配比评分应>0.50，实际={res['quality_score']}"
    assert res["compaction_ratio"] >= 0.70, f"压实度应>0.70: {res['compaction_ratio']}"
    print(f"   最优配比 -> 评分={res['quality_score']:.2f}, 等级={res['quality_rating']}, 压实度={res['compaction_ratio']:.2f}")

run_test("4.8 边界场景-最优配比验证", test_virtual_boundary_extreme_quality)

# --- 异常场景 ---
def test_virtual_abnormal_bad_mix():
    bad_mix = {"soil_pct": 5, "clay_pct": 5, "sand_pct": 80,
               "lime_pct": 0, "rice_paste_pct": 0, "straw_pct": 0, "water_pct": 10}
    res = virtual_experience_service.evaluate_mix(bad_mix, "light", 2.5, 8.0)
    assert res["quality_rating"] in ["差", "劣"], f"差配比应得差或劣，实际={res['quality_rating']}"
    assert res["quality_score"] < 0.5, f"评分应<0.5: {res['quality_score']}"
    assert len(res["suggestions"]) >= 3, "差配比应有更多改进建议"
    print(f"   劣质配比 -> 评分={res['quality_score']:.2f}, 等级={res['quality_rating']}")
    print(f"   建议数: {len(res['suggestions'])}条 - 教育性验证通过")

run_test("4.9 异常场景-劣质配比教育性", test_virtual_abnormal_bad_mix)

def test_virtual_abnormal_invalid_tamping():
    mix_dict = {
        "soil_pct": 65, "clay_pct": 15, "sand_pct": 10,
        "lime_pct": 3, "rice_paste_pct": 2, "straw_pct": 1, "water_pct": 16
    }
    res = virtual_experience_service.evaluate_mix(mix_dict, "INVALID_TAMPING", 2.5, 8.0)
    assert res is not None, "无效夯打预设应仍有默认处理"
    assert res["compaction_ratio"] > 0, "压实度不应为0"
    print(f"   无效夯打预设 -> 默认处理 (正确)")

run_test("4.10 异常场景-无效夯打预设", test_virtual_abnormal_invalid_tamping)

def test_virtual_abnormal_extreme_values():
    extreme_mix = {"soil_pct": 40, "clay_pct": 30, "sand_pct": 25,
                   "lime_pct": 15, "rice_paste_pct": 8, "straw_pct": 5, "water_pct": 22}
    res = virtual_experience_service.evaluate_mix(extreme_mix, "heavy", 2.5, 8.0)
    assert 0.0 <= res["quality_score"] <= 1.0
    assert res["hardness_mpa"] > 0
    assert res["erosion_rate_mm_per_year"] > 0
    print(f"   边界值配比 -> 评分={res['quality_score']:.2f} (数值稳定性验证通过)")

run_test("4.11 异常场景-极端值稳定性", test_virtual_abnormal_extreme_values)

def test_virtual_abnormal_educational_suggestions():
    mix_dict = {
        "soil_pct": 65, "clay_pct": 15, "sand_pct": 10,
        "lime_pct": 2, "rice_paste_pct": 1, "straw_pct": 0, "water_pct": 10
    }
    res = virtual_experience_service.evaluate_mix(mix_dict, "light", 2.5, 8.0)
    suggestions = res["suggestions"]
    has_water_suggestion = any("含水量" in s for s in suggestions)
    has_lime_suggestion = any("石灰" in s or "糯米汁" in s for s in suggestions)
    has_tamping_suggestion = any("夯实度" in s or "夯打" in s for s in suggestions)
    assert has_water_suggestion, "应提示含水量问题"
    assert has_lime_suggestion, "应提示胶结材料问题"
    print(f"   教育性建议 -> 含水量提示:{has_water_suggestion}, 材料提示:{has_lime_suggestion}")
    for i, s in enumerate(suggestions[:3]):
        print(f"   建议{i+1}: {s}")

run_test("4.12 异常场景-教育建议内容验证", test_virtual_abnormal_educational_suggestions)

# ======================================================================
# 综合验证: 物理一致性
# ======================================================================
print("\n" + "=" * 75)
print("🔬 综合验证: 物理规律一致性检查")
print("=" * 75)

def test_physical_wind_erosion_monotonicity():
    dyn_res = dynasty_comparison_service.compare_dynasties(
        ["QIN"], 4.0, 5.0, 24, None
    )
    rate_low = dyn_res["results"][0]["erosion_rate_mm_per_year"]
    dyn_res2 = dynasty_comparison_service.compare_dynasties(
        ["QIN"], 16.0, 5.0, 24, None
    )
    rate_high = dyn_res2["results"][0]["erosion_rate_mm_per_year"]
    assert rate_high > rate_low, f"风速增大侵蚀率应增加: 4m/s={rate_low:.4f}, 16m/s={rate_high:.4f}"
    print(f"   ✓ 风蚀率随风速递增: 4m/s -> {rate_low:.4f}, 16m/s -> {rate_high:.4f}")

run_test("物理1: 风蚀率-风速单调性", test_physical_wind_erosion_monotonicity)

def test_physical_hardness_erosion_inverse():
    dyn_res = dynasty_comparison_service.compare_dynasties(
        ["HAN", "QIN"], 8.0, 5.0, 24, None
    )
    han = [r for r in dyn_res["results"] if r["dynasty_code"] == "HAN"][0]
    qin = [r for r in dyn_res["results"] if r["dynasty_code"] == "QIN"][0]
    assert qin["hardness_mpa"] > han["hardness_mpa"], "秦代硬度应高于汉代"
    assert qin["erosion_rate_mm_per_year"] < han["erosion_rate_mm_per_year"], "秦代侵蚀率应低于汉代"
    print(f"   ✓ 硬度与侵蚀率负相关: 秦(硬={qin['hardness_mpa']:.2f}, 蚀={qin['erosion_rate_mm_per_year']:.4f}) < 汉")

run_test("物理2: 硬度-侵蚀率负相关", test_physical_hardness_erosion_inverse)

def test_physical_coverage_effect_monotonicity():
    rates = []
    for cov in [0, 30, 60, 90]:
        req = PlantRootSimulationRequest(
            plant_codes=["SHRUB"], coverage_pct=float(cov),
            wall_height_m=2.5, wind_speed=8.0, soil_moisture=5.0, season="summer"
        )
        res = plant_root_service.simulate_plant_protection(
            req.plant_codes, req.coverage_pct, req.wall_height_m,
            req.wind_speed, req.soil_moisture, req.season
        )
        rates.append((cov, res["total_reduction_pct"]))
    for i in range(len(rates) - 1):
        assert rates[i+1][1] >= rates[i][1], f"覆盖率增加防护效果应递增: {rates[i]} -> {rates[i+1]}"
    print(f"   ✓ 防护效果随覆盖率递增: {[f'{c}%->{r:.1f}%' for c, r in rates]}")

run_test("物理3: 覆盖率-防护效果单调性", test_physical_coverage_effect_monotonicity)

# ======================================================================
# 测试汇总
# ======================================================================
print("\n" + "=" * 75)
print("📊 测试结果汇总")
print("=" * 75)
print(f"\n总计: {len(tests)} 个测试用例")
print(f"✅ 通过: {passed}")
print(f"❌ 失败: {failed}")
print()
if failed > 0:
    print("失败详情:")
    for name, status, detail in tests:
        if status != "PASS":
            print(f"  {name}: {status} - {detail}")
else:
    print("🎉 所有测试通过！")
print()
print("覆盖维度:")
print("  🏺 朝代工艺对比: 9个用例 (正常3 + 边界4 + 异常2)")
print("  ⚒️  跨时代工程对比: 9个用例 (正常3 + 边界4 + 异常2)")
print("  🌱 植物根系防护: 11个用例 (正常3 + 边界5 + 异常3)")
print("  👐 虚拟夯土体验: 12个用例 (正常3 + 边界6 + 异常3)")
print("  🔬 物理一致性: 3个用例")
print(f"\n覆盖率: 正常({len([t for t in tests if '正常' in t[0]])}) + "
      f"边界({len([t for t in tests if '边界' in t[0]])}) + "
      f"异常({len([t for t in tests if '异常' in t[0]])}) + "
      f"物理({len([t for t in tests if '物理' in t[0]])}) = {len(tests)}")
