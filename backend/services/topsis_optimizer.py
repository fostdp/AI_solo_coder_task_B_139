import numpy as np
from typing import List, Dict, Any, Tuple
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from ..models.orm import ReinforcementPlan, ReinforcementMaterial, WallSegment
from ..models.schemas import TOPSISEvaluationRequest, TOPSISEvaluationResult


class TOPSISEvaluator:
    def __init__(self):
        self.default_criteria = [
            "penetration_depth",
            "durability_years",
            "cost_per_sqm",
            "construction_difficulty",
            "environmental_impact",
            "durability_confidence"
        ]
        self.default_weights = {
            "penetration_depth": 0.25,
            "durability_years": 0.25,
            "cost_per_sqm": 0.20,
            "construction_difficulty": 0.10,
            "environmental_impact": 0.10,
            "durability_confidence": 0.10
        }
        self.default_benefit = ["penetration_depth", "durability_years", "durability_confidence"]
        self.default_cost = ["cost_per_sqm", "construction_difficulty", "environmental_impact"]
        
        # 加速老化实验参数
        self.ACTIVATION_ENERGY = {
            "TEOS-01": 65.0,    # 硅酸乙酯 活化能 (kJ/mol)
            "TEOS-02": 58.0,    # 改性硅酸乙酯
            "GLU-01": 52.0,     # 糯米灰浆
            "GLU-02": 55.0,     # 改性糯米灰浆
            "COM-01": 60.0,      # 复合加固剂
        }
        self.GAS_CONSTANT = 8.314  # J/(mol·K)
        
        # 参考温度 (标准实验室温度 (°C)
        self.REF_TEMPERATURE = 25.0
        self.ACC_TEMPERATURE = 60.0  # 加速老化温度 (°C)
        self.ACC_HUMIDITY = 90.0   # 加速老化湿度 (%)
        self.REF_HUMIDITY = 60.0     # 参考湿度 (%)
        self.ACC_CYCLES_PER_DAY = 2  # 盐雾循环次数/天
        self.REF_CYCLES_PER_YEAR = 50  # 自然环境年循环次数
        
        # 湿度加速系数
        self.HUMIDITY_ACCELERATION_FACTOR = 2.5  # 湿度加速指数因子

        # 老化实验周期 (天)
        self.AGING_TEST_DURATION_DAYS = 90  # 加速老化实验时长(天)
        self.MIN_STRENGTH_RETENTION = {
            "TEOS-01": 0.85,  # 90天加速老化后强度保留率
            "TEOS-02": 0.90,
            "GLU-01": 0.75,
            "GLU-02": 0.80,
            "COM-01": 0.82,
        }
        
        # 性能退化阈值
        self.FAILURE_THRESHOLD = 0.5  # 强度保留率低于50%视为失效

    def _normalize_matrix(self, matrix: np.ndarray) -> np.ndarray:
        norms = np.sqrt(np.sum(matrix**2, axis=0))
        norms = np.where(norms == 0, 1, norms)
        return matrix / norms

    def _apply_weights(self, normalized_matrix: np.ndarray, weights: np.ndarray) -> np.ndarray:
        return normalized_matrix * weights

    def _find_ideal_solutions(
        self,
        weighted_matrix: np.ndarray,
        benefit_indices: List[int],
        cost_indices: List[int]
    ) -> Tuple[np.ndarray, np.ndarray]:
        positive_ideal = np.copy(weighted_matrix[0])
        negative_ideal = np.copy(weighted_matrix[0])
        
        for j in range(weighted_matrix.shape[1]):
            if j in benefit_indices:
                positive_ideal[j] = np.max(weighted_matrix[:, j])
                negative_ideal[j] = np.min(weighted_matrix[:, j])
            else:
                positive_ideal[j] = np.min(weighted_matrix[:, j])
                negative_ideal[j] = np.max(weighted_matrix[:, j])
        
        return positive_ideal, negative_ideal

    def _calculate_distances(
        self,
        weighted_matrix: np.ndarray,
        positive_ideal: np.ndarray,
        negative_ideal: np.ndarray
    ) -> Tuple[np.ndarray, np.ndarray]:
        d_positive = np.sqrt(np.sum((weighted_matrix - positive_ideal)**2, axis=1))
        d_negative = np.sqrt(np.sum((weighted_matrix - negative_ideal)**2, axis=1))
        return d_positive, d_negative

    def _calculate_closeness(self, d_positive: np.ndarray, d_negative: np.ndarray) -> np.ndarray:
        total = d_positive + d_negative
        total = np.where(total == 0, 1, total)
        return d_negative / total

    def evaluate(
        self,
        alternatives: List[Dict[str, Any]],
        criteria: List[str],
        weights: Dict[str, float],
        benefit_criteria: List[str],
        cost_criteria: List[str]
    ) -> List[Dict[str, Any]]:
        if not alternatives:
            return []
        
        n_alternatives = len(alternatives)
        n_criteria = len(criteria)
        
        matrix = np.zeros((n_alternatives, n_criteria))
        criteria_to_idx = {c: i for i, c in enumerate(criteria)}
        
        for i, alt in enumerate(alternatives):
            for j, crit in enumerate(criteria):
                value = alt.get(crit, 0)
                if value is None:
                    value = 0
                matrix[i, j] = float(value)
        
        weight_array = np.array([weights.get(c, 1.0/n_criteria) for c in criteria])
        
        normalized = self._normalize_matrix(matrix)
        weighted = self._apply_weights(normalized, weight_array)
        
        benefit_indices = [criteria_to_idx[c] for c in benefit_criteria if c in criteria_to_idx]
        cost_indices = [criteria_to_idx[c] for c in cost_criteria if c in criteria_to_idx]
        
        positive_ideal, negative_ideal = self._find_ideal_solutions(
            weighted, benefit_indices, cost_indices
        )
        
        d_pos, d_neg = self._calculate_distances(weighted, positive_ideal, negative_ideal)
        closeness = self._calculate_closeness(d_pos, d_neg)
        
        ranked_indices = np.argsort(-closeness)
        
        results = []
        for rank, idx in enumerate(ranked_indices, 1):
            alt = alternatives[idx]
            criteria_scores = {}
            for j, crit in enumerate(criteria):
                criteria_scores[crit] = float(weighted[idx, j])
            
            results.append({
                "plan_id": alt.get("id"),
                "plan_name": alt.get("plan_name"),
                "material_type": alt.get("material_type"),
                "topsis_score": float(closeness[idx]),
                "topsis_rank": rank,
                "criteria_scores": criteria_scores,
                "d_positive": float(d_pos[idx]),
                "d_negative": float(d_neg[idx]),
                "is_selected": rank == 1
            })
        
        return results

    def calculate_penetration_depth(
        self,
        material_code: str,
        material_ratio: str,
        surface_hardness: float,
        soil_moisture: float,
        application_pressure: float = 0.5
    ) -> float:
        material_coefficients = {
            "TEOS-01": {"alpha": 0.75, "beta": 0.02, "gamma": 0.15},
            "TEOS-02": {"alpha": 0.68, "beta": 0.025, "gamma": 0.18},
            "GLU-01": {"alpha": 0.45, "beta": 0.015, "gamma": 0.10},
            "GLU-02": {"alpha": 0.52, "beta": 0.018, "gamma": 0.12},
            "COM-01": {"alpha": 0.60, "beta": 0.022, "gamma": 0.14}
        }
        
        coeff = material_coefficients.get(material_code, {"alpha": 0.5, "beta": 0.02, "gamma": 0.12})
        
        hardness_factor = np.exp(-coeff["beta"] * surface_hardness)
        moisture_factor = np.exp(-coeff["gamma"] * soil_moisture)
        pressure_factor = np.sqrt(application_pressure / 0.5)
        
        base_depth = 10.0
        penetration_depth = base_depth * coeff["alpha"] * hardness_factor * moisture_factor * pressure_factor
        
        return max(1.0, min(50.0, penetration_depth))

    def calculate_arrhenius_factor(
        self,
        material_code: str,
        acc_temperature: float = None,
        ref_temperature: float = None
    ) -> float:
        """
        Arrhenius温度加速因子
        AF_temp = exp[(Ea/R) * (1/T_ref - 1/T_acc)
        """
        Ea = self.ACTIVATION_ENERGY.get(material_code, 60.0) * 1000  # J/mol
        R = self.GAS_CONSTANT
        
        T_ref = (ref_temperature or self.REF_TEMPERATURE) + 273.15  # K
        T_acc = (acc_temperature or self.ACC_TEMPERATURE) + 273.15  # K
        
        af_temperature = np.exp((Ea / R) * (1.0 / T_ref - 1.0 / T_acc))
        
        return af_temperature

    def calculate_humidity_acceleration(
        self,
        acc_humidity: float = None,
        ref_humidity: float = None
    ) -> float:
        """
        湿度加速因子
        基于Peck模型: AF_humidity = exp(n * n * ΔRH
        """
        RH_acc = acc_humidity or self.ACC_HUMIDITY
        RH_ref = ref_humidity or self.REF_HUMIDITY
        n = self.HUMIDITY_ACCELERATION_FACTOR
        
        af_humidity = np.exp(n * (RH_acc - RH_ref) / 100.0)
        
        return af_humidity

    def calculate_cycle_acceleration(
        self,
        acc_cycles_per_day: float = None,
        ref_cycles_per_year: float = None
    ) -> float:
        """
        盐雾/干湿循环加速因子
        """
        acc_cycles = acc_cycles_per_day or self.ACC_CYCLES_PER_DAY
        ref_cycles = ref_cycles_per_year or self.REF_CYCLES_PER_YEAR
        acc_yearly = acc_cycles * 365
        return acc_yearly / ref_cycles if ref_cycles > 0 else 1.0

    def calculate_total_acceleration_factor(
        self,
        material_code: str,
        temperature_factor_weight: float = 0.5,
        humidity_factor_weight: float = 0.3,
        cycle_factor_weight: float = 0.2
    ) -> Dict[str, float]:
        """
        综合加速因子（加权综合加速因子
        考虑温度、湿度、循环三种加速效应，按权重综合加速因子
        """
        af_temp = self.calculate_arrhenius_factor(material_code)
        af_hum = self.calculate_humidity_acceleration()
        af_cycle = self.calculate_cycle_acceleration()
        
        # 综合加速因子（加权几何平均
        af_total = (af_temp ** temperature_factor_weight * 
                  af_hum ** humidity_factor_weight * 
                  af_cycle ** cycle_factor_weight)
        
        return {
            "temperature_factor": af_temp,
            "humidity_factor": af_hum,
            "cycle_factor": af_cycle,
            "total_factor": af_total,
            "total_days_per_year": 365 / af_total  # 加速1年相当于自然多少年
        }

    def calculate_degradation_rate(
        self,
        material_code: str,
        strength_retention: float,
        test_duration_days: float = None
    ) -> float:
        """
        计算性能退化速率 (假设指数退化模型)
        R(t) = exp(-k * t)  强度保留率
        k = -ln(R) / t
        """
        t_days = test_duration_days or self.AGING_TEST_DURATION_DAYS
        R = max(0.01, min(0.99, strength_retention))
        
        k_daily = -np.log(R) / t_days  # 每日退化率
        return k_daily

    def extrapolate_lifespan(
        self,
        material_code: str,
        strength_retention: float = None,
        test_duration_days: float = None,
        failure_threshold: float = None
    ) -> Dict[str, float]:
        """
        基于加速老化实验的寿命外推
        使用Arrhenius+湿度+循环综合加速
        """
        R = strength_retention or self.MIN_STRENGTH_RETENTION.get(material_code, 0.8)
        test_days = test_duration_days or self.AGING_TEST_DURATION_DAYS
        threshold = failure_threshold or self.FAILURE_THRESHOLD
        
        acc_factors = self.calculate_total_acceleration_factor(material_code)
        af_total = acc_factors["total_factor"]
        
        # 加速条件下的退化速率
        k_acc = self.calculate_degradation_rate(material_code, R, test_days)
        
        # 自然条件下的退化速率
        k_natural = k_acc / af_total
        
        # 外推到失效阈值的时间
        t_failure_acc = -np.log(threshold) / k_acc  # 加速条件下失效时间(天)
        t_failure_natural = -np.log(threshold) / k_natural  # 自然条件下失效时间(天)
        
        # 加速条件下90天保留率
        # 外推到自然条件下的寿命(年)
        lifespan_years_natural = t_failure_natural / 365.0
        
        return {
            "acceleration_factors": acc_factors,
            "degradation_rate_acc": k_acc,
            "degradation_rate_natural": k_natural,
            "test_duration_days": test_days,
            "failure_time_acc_days": t_failure_acc,
            "lifespan_years": lifespan_years_natural,
            "strength_retention_90d_acc": R,
            "failure_threshold": threshold
        }

    def calculate_confidence_interval(
        self,
        material_code: str,
        sample_count: int = 5,
        confidence_level: float = 0.95
    ) -> Dict[str, float]:
        """
        寿命估计的置信区间
        基于对数正态分布假设
        """
        lifespan_data = self.extrapolate_lifespan(material_code)
        lifespan = lifespan_data["lifespan_years"]
        
        # 变异系数 (假设20%的变异系数
        cv = 0.2
        
        # 标准误
        se = lifespan * cv / np.sqrt(sample_count)
        
        # 置信区间（近似正态近似）
        z_score = 1.96  # 95%置信度
        lower = max(1, lifespan - z_score * se)
        upper = lifespan + z_score * se
        
        return {
            "point_estimate": lifespan,
            "standard_error": se,
            "lower_bound": lower,
            "upper_bound": upper,
            "confidence_level": confidence_level,
            "coefficient_of_variation": cv
        }

    def run_accelerated_aging_simulation(
        self,
        material_code: str,
        test_temperature: float = 60.0,
        test_humidity: float = 90.0,
        test_days: int = 90,
        initial_strength: float = 1.0
    ) -> List[Dict[str, Any]]:
        """
        模拟加速老化实验过程
        返回不同时间点的强度保留率数据
        """
        # 计算该温度和湿度下的退化速率
        Ea = self.ACTIVATION_ENERGY.get(material_code, 60.0) * 1000
        R = self.GAS_CONSTANT
        
        T_ref = self.REF_TEMPERATURE + 273.15
        T_test = test_temperature + 273.15
        
        af_temp = np.exp((Ea / R) * (1.0 / T_ref - 1.0 / T_test))
        af_hum = self.calculate_humidity_acceleration(test_humidity, self.REF_HUMIDITY)
        af_total = af_temp * af_hum ** 0.5  # 温度和湿度的耦合效应
        
        # 参考条件下的基础退化率（假设参考条件下的退化率
        k_ref = 0.001  # 参考退化率/天（参考条件
        k_test = k_ref * af_total
        
        # 生成时间序列数据点
        time_points = [1, 3, 7, 14, 28, 60, 90]
        results = []
        
        for t in time_points:
            if t <= test_days:
                strength = initial_strength * np.exp(-k_test * t)
                equivalent_natural_days = t / af_total
                
                results.append({
                    "test_day": t,
                    "strength_retention": strength,
                    "equivalent_natural_days": equivalent_natural_days,
                    "equivalent_natural_years": equivalent_natural_days / 365.0
                })
        
        return results

    def calculate_durability(
        self,
        material_code: str,
        penetration_depth: float,
        environment_factor: float = 1.0
    ) -> float:
        """
        基于加速老化实验外推的耐用年限计算
        """
        # 加速老化外推得到基础寿命
        lifespan_data = self.extrapolate_lifespan(material_code)
        base_lifespan = lifespan_data["lifespan_years"]
        
        # 渗透深度修正（越深越耐久
        penetration_factor = penetration_depth / 15.0
        penetration_factor = max(0.5, min(2.0, penetration_factor))
        
        # 环境因子修正
        durability = base_lifespan * penetration_factor * environment_factor
        
        return max(3.0, durability)

    def calculate_durability_with_confidence(
        self,
        material_code: str,
        penetration_depth: float,
        environment_factor: float = 1.0
    ) -> Dict[str, Any]:
        """
        带置信区间的耐用年限计算
        """
        lifespan_data = self.extrapolate_lifespan(material_code)
        confidence = self.calculate_confidence_interval(material_code)
        
        penetration_factor = penetration_depth / 15.0
        penetration_factor = max(0.5, min(2.0, penetration_factor))
        
        return {
            "base_lifespan_years": lifespan_data["lifespan_years"] * penetration_factor * environment_factor,
            "lower_bound_years": confidence["lower_bound"] * penetration_factor * environment_factor,
            "upper_bound_years": confidence["upper_bound"] * penetration_factor * environment_factor,
            "confidence_level": confidence["confidence_level"],
            "degradation_rate": lifespan_data["degradation_rate_natural"],
            "acceleration_factor": lifespan_data["acceleration_factors"]["total_factor"],
            "test_data_points": lifespan_data.get("test_duration_days", 90)
        }

    def calculate_environmental_impact(
        self,
        material_code: str,
        quantity: float = 1.0
    ) -> float:
        impact_factors = {
            "TEOS-01": 0.7,
            "TEOS-02": 0.85,
            "GLU-01": 0.15,
            "GLU-02": 0.20,
            "COM-01": 0.45
        }
        return impact_factors.get(material_code, 0.5) * quantity

    def calculate_cost(
        self,
        material_code: str,
        area: float,
        penetration_depth: float,
        material_cost_per_kg: float,
        application_cost_per_sqm: float = 15.0
    ) -> float:
        consumption_rate = 1.5
        material_quantity = area * (penetration_depth / 1000) * consumption_rate
        material_cost = material_quantity * material_cost_per_kg
        application_cost = area * application_cost_per_sqm
        total_cost = material_cost + application_cost
        return total_cost

    def generate_reinforcement_plans(
        self,
        segment_id: int,
        segment_area: float,
        avg_hardness: float,
        avg_moisture: float,
        erosion_severity: str = "medium"
    ) -> List[Dict[str, Any]]:
        materials = [
            {"code": "TEOS-01", "name": "硅酸乙酯", "ratio": "100%", "cost_kg": 45.0, "difficulty": 6},
            {"code": "TEOS-02", "name": "改性硅酸乙酯", "ratio": "TEOS+10%纳米SiO2", "cost_kg": 68.0, "difficulty": 7},
            {"code": "GLU-01", "name": "糯米灰浆", "ratio": "糯米:石灰=1:3", "cost_kg": 12.0, "difficulty": 3},
            {"code": "GLU-02", "name": "改性糯米灰浆", "ratio": "糯米:石灰:纳米CaO=1:3:0.1", "cost_kg": 18.0, "difficulty": 4},
            {"code": "COM-01", "name": "复合加固剂", "ratio": "TEOS:GLU=1:1", "cost_kg": 38.0, "difficulty": 8}
        ]
        
        severity_multiplier = {
            "low": 1.0,
            "medium": 1.2,
            "high": 1.5
        }
        mult = severity_multiplier.get(erosion_severity, 1.2)
        
        plans = []
        for mat in materials:
            penetration = self.calculate_penetration_depth(
                mat["code"], mat["ratio"], avg_hardness, avg_moisture
            ) * mult
            
            durability = self.calculate_durability(mat["code"], penetration)
            
            # 带置信区间的耐用年限
            durability_conf = self.calculate_durability_with_confidence(
                mat["code"], penetration
            )
            
            # 耐用年限置信度（上下界距离点估计的相对偏差的倒数
            confidence = 1.0 - (durability_conf["upper_bound_years"] - durability_conf["lower_bound_years"]) / (2 * durability_conf["base_lifespan_years"])
            confidence = max(0.5, min(0.95, confidence))
            
            env_impact = self.calculate_environmental_impact(mat["code"], segment_area)
            cost_per_sqm = self.calculate_cost(mat["code"], 1.0, penetration, mat["cost_kg"])
            
            # 加速老化实验数据
            aging_data = self.run_accelerated_aging_simulation(mat["code"])
            acc_factors = self.calculate_total_acceleration_factor(mat["code"])
            
            plans.append({
                "segment_id": segment_id,
                "plan_name": f"{mat['name']}加固方案",
                "material_type": mat["code"],
                "material_ratio": mat["ratio"],
                "penetration_depth": round(penetration, 2),
                "cost_per_sqm": round(cost_per_sqm, 2),
                "construction_difficulty": mat["difficulty"],
                "durability_years": round(durability, 1),
                "durability_confidence": round(confidence, 3),
                "durability_lower_bound": round(durability_conf["lower_bound_years"], 1),
                "durability_upper_bound": round(durability_conf["upper_bound_years"], 1),
                "environmental_impact": round(env_impact, 3),
                "aging_test_data": aging_data,
                "acceleration_factors": acc_factors
            })
        
        return plans

    async def evaluate_segment_plans(
        self,
        db: AsyncSession,
        request: TOPSISEvaluationRequest
    ) -> List[TOPSISEvaluationResult]:
        stmt = (
            select(ReinforcementPlan)
            .where(ReinforcementPlan.segment_id == request.segment_id)
            .order_by(ReinforcementPlan.created_at.desc())
        )
        result = await db.execute(stmt)
        plans = result.scalars().all()
        
        if not plans:
            segment = await db.get(WallSegment, request.segment_id)
            if not segment:
                raise ValueError(f"Segment {request.segment_id} not found")
            
            area = segment.length_m * segment.height_m
            avg_hardness = 2.5
            avg_moisture = 5.0
            
            generated_plans = self.generate_reinforcement_plans(
                request.segment_id, area, avg_hardness, avg_moisture, "medium"
            )
            
            for p in generated_plans:
                db_plan = ReinforcementPlan(**p)
                db.add(db_plan)
            await db.flush()
            
            result = await db.execute(stmt)
            plans = result.scalars().all()
        
        alternatives = []
        for plan in plans:
            alternatives.append({
                "id": plan.id,
                "plan_name": plan.plan_name,
                "material_type": plan.material_type,
                "penetration_depth": plan.penetration_depth or 0,
                "durability_years": plan.durability_years or 0,
                "durability_confidence": plan.durability_confidence or 0.7,
                "cost_per_sqm": plan.cost_per_sqm or 0,
                "construction_difficulty": plan.construction_difficulty or 0,
                "environmental_impact": plan.environmental_impact or 0
            })
        
        results = self.evaluate(
            alternatives,
            self.default_criteria,
            request.weights,
            request.benefit_criteria,
            request.cost_criteria
        )
        
        for res in results:
            plan = await db.get(ReinforcementPlan, res["plan_id"])
            if plan:
                plan.topsis_score = res["topsis_score"]
                plan.topsis_rank = res["topsis_rank"]
                plan.is_selected = res["is_selected"]
        
        await db.commit()
        
        return [TOPSISEvaluationResult(**r) for r in results]


topsis_evaluator = TOPSISEvaluator()
