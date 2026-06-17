import asyncio
import logging
import numpy as np
from typing import Any, Dict, List, Optional
from .common import get_materials_config, get_message_bus, RedisMessageBus

logger = logging.getLogger("reinforcement_optimizer")


class ReinforcementOptimizerService:
    def __init__(self, bus: RedisMessageBus = None):
        self.cfg = get_materials_config()
        self.bus = bus
        self.materials = self.cfg.get("materials", {})
        self.aging_cfg = self.cfg.get("accelerated_aging", {})
        self.severity_map = self.cfg.get("erosion_severity_map", {})
        self.criteria_defaults = self.cfg.get("criteria_defaults", {})

    async def ensure_bus(self):
        if self.bus is None:
            self.bus = await get_message_bus()

    def _get_material(self, material_code: str) -> Dict[str, Any]:
        return self.materials.get(material_code, {})

    def calculate_penetration_depth(
        self,
        material_code: str,
        material_ratio: str,
        surface_hardness: float,
        soil_moisture: float,
        application_pressure: float = 0.5,
    ) -> float:
        mat = self._get_material(material_code)
        coeff = mat.get("penetration_coefficients", {"alpha": 0.5, "beta": 0.02, "gamma": 0.12})
        alpha = coeff.get("alpha", 0.5)
        beta = coeff.get("beta", 0.02)
        gamma = coeff.get("gamma", 0.12)

        ratio_factor = 1.0
        if material_ratio and "+" in material_ratio:
            try:
                parts = material_ratio.split("+")
                if len(parts) == 2:
                    p1 = float(parts[0].replace("%", "")) / 100.0
                    ratio_factor = p1 + 0.9 * (1.0 - p1)
            except ValueError:
                pass

        depth = 10.0 * alpha * np.exp(-beta * surface_hardness) * np.exp(-gamma * soil_moisture) * np.sqrt(application_pressure / 0.5)
        depth = depth * ratio_factor

        return float(max(1.0, min(50.0, depth)))

    def calculate_arrhenius_factor(
        self,
        material_code: str,
        acc_T: float,
        ref_T: float,
    ) -> float:
        mat = self._get_material(material_code)
        Ea_kj = mat.get("activation_energy_kj_mol", 60.0)
        R = self.aging_cfg.get("gas_constant", 8.314)
        Ea = Ea_kj * 1000.0
        T_ref = ref_T + 273.15
        T_acc = acc_T + 273.15
        return float(np.exp((Ea / R) * (1.0 / T_ref - 1.0 / T_acc)))

    def calculate_humidity_acceleration(
        self,
        acc_RH: float,
        ref_RH: float,
        n: float = 2.5,
    ) -> float:
        n_val = self.aging_cfg.get("humidity_acceleration_n", n)
        return float(np.exp(n_val * (acc_RH - ref_RH) / 100.0))

    def calculate_cycle_acceleration(
        self,
        acc_cycles_per_day: float,
        ref_cycles_per_year: float,
    ) -> float:
        if ref_cycles_per_year <= 0:
            return 1.0
        acc_yearly = acc_cycles_per_day * 365.0
        return float(acc_yearly / ref_cycles_per_year)

    def calculate_total_acceleration_factor(
        self,
        material_code: str,
        acc_T: float = None,
        ref_T: float = None,
        acc_RH: float = None,
        ref_RH: float = None,
        acc_cycles_per_day: float = None,
        ref_cycles_per_year: float = None,
    ) -> Dict[str, float]:
        acc_T_val = acc_T if acc_T is not None else self.aging_cfg.get("acc_temperature_c", 60.0)
        ref_T_val = ref_T if ref_T is not None else self.aging_cfg.get("ref_temperature_c", 25.0)
        acc_RH_val = acc_RH if acc_RH is not None else self.aging_cfg.get("acc_humidity_pct", 90.0)
        ref_RH_val = ref_RH if ref_RH is not None else self.aging_cfg.get("ref_humidity_pct", 60.0)
        acc_cyc_val = acc_cycles_per_day if acc_cycles_per_day is not None else self.aging_cfg.get("acc_cycles_per_day", 2.0)
        ref_cyc_val = ref_cycles_per_year if ref_cycles_per_year is not None else self.aging_cfg.get("ref_cycles_per_year", 50.0)

        AF_T = self.calculate_arrhenius_factor(material_code, acc_T_val, ref_T_val)
        AF_H = self.calculate_humidity_acceleration(acc_RH_val, ref_RH_val)
        AF_C = self.calculate_cycle_acceleration(acc_cyc_val, ref_cyc_val)

        AF_total = (AF_T ** 0.5) * (AF_H ** 0.3) * (AF_C ** 0.2)

        return {
            "temperature_factor": float(AF_T),
            "humidity_factor": float(AF_H),
            "cycle_factor": float(AF_C),
            "total_factor": float(AF_total),
        }

    def calculate_degradation_rate(
        self,
        strength_retention: float,
        days: float,
    ) -> float:
        R = max(0.01, min(0.99, strength_retention))
        if days <= 0:
            return 0.0
        return float(-np.log(R) / days)

    def extrapolate_lifespan(
        self,
        k_acc: float,
        AF: float,
        threshold: float = 0.5,
    ) -> float:
        if k_acc <= 0 or AF <= 0:
            return 0.0
        t_failure_natural_days = -np.log(threshold) * 365.0 / (k_acc * AF)
        return float(t_failure_natural_days / 365.0)

    def calculate_confidence_interval(
        self,
        lifespan: float,
        cv: float = 0.2,
    ) -> Dict[str, float]:
        cv_val = self.aging_cfg.get("coefficient_of_variation", cv)
        z = self.aging_cfg.get("confidence_coefficient", 1.96)

        if lifespan <= 0:
            return {"lower": 0.0, "upper": 0.0, "lifespan": 0.0}

        sigma_ln = np.sqrt(np.log(1.0 + cv_val ** 2))
        mu_ln = np.log(lifespan) - 0.5 * sigma_ln ** 2

        lower_ln = mu_ln - z * sigma_ln
        upper_ln = mu_ln + z * sigma_ln

        return {
            "lifespan": float(lifespan),
            "lower": float(max(0.1, np.exp(lower_ln))),
            "upper": float(np.exp(upper_ln)),
            "cv": float(cv_val),
            "confidence_level": 0.95,
        }

    def run_accelerated_aging_simulation(
        self,
        material_code: str,
        test_temperature: float = None,
        test_humidity: float = None,
        test_days: int = None,
        initial_strength: float = 1.0,
    ) -> List[Dict[str, Any]]:
        test_T = test_temperature if test_temperature is not None else self.aging_cfg.get("acc_temperature_c", 60.0)
        test_RH = test_humidity if test_humidity is not None else self.aging_cfg.get("acc_humidity_pct", 90.0)
        t_days = test_days if test_days is not None else self.aging_cfg.get("aging_test_duration_days", 90)
        ref_T = self.aging_cfg.get("ref_temperature_c", 25.0)
        ref_RH = self.aging_cfg.get("ref_humidity_pct", 60.0)

        mat = self._get_material(material_code)
        retention_90d = mat.get("strength_retention_90d", 0.82)

        AF_T = self.calculate_arrhenius_factor(material_code, test_T, ref_T)
        AF_H = self.calculate_humidity_acceleration(test_RH, ref_RH)
        AF_total = (AF_T ** 0.5) * (AF_H ** 0.5)

        k_acc = -np.log(max(0.01, retention_90d)) / 90.0
        k_test = k_acc * AF_total

        time_points = [1, 3, 7, 14, 28, 60, 90]
        results = []
        for t in time_points:
            if t <= t_days:
                strength = initial_strength * np.exp(-k_test * t)
                equiv_natural_days = t / max(AF_total, 1e-6)
                results.append({
                    "test_day": int(t),
                    "strength_retention": float(strength),
                    "equivalent_natural_days": float(equiv_natural_days),
                    "equivalent_natural_years": float(equiv_natural_days / 365.0),
                })
        return results

    def calculate_durability_with_confidence(
        self,
        material_code: str,
        penetration_depth: float,
    ) -> Dict[str, Any]:
        mat = self._get_material(material_code)
        retention_90d = mat.get("strength_retention_90d", 0.82)
        test_days = self.aging_cfg.get("aging_test_duration_days", 90)
        threshold = self.aging_cfg.get("failure_threshold_retention", 0.5)

        af_data = self.calculate_total_acceleration_factor(material_code)
        AF = af_data["total_factor"]

        k_acc = self.calculate_degradation_rate(retention_90d, test_days)

        base_lifespan = self.extrapolate_lifespan(k_acc, AF, threshold)

        penetration_factor = penetration_depth / 15.0
        penetration_factor = max(0.5, min(2.0, penetration_factor))

        lifespan = base_lifespan * penetration_factor

        ci = self.calculate_confidence_interval(lifespan)

        ci_width = ci["upper"] - ci["lower"]
        confidence = 1.0 - (ci_width / (2.0 * max(lifespan, 1e-6)))
        confidence = float(max(0.5, min(0.95, confidence)))

        return {
            "years": float(lifespan),
            "confidence": confidence,
            "lower": float(ci["lower"]),
            "upper": float(ci["upper"]),
            "AF": float(AF),
            "test_days": int(test_days),
            "retention": float(retention_90d),
        }

    def calculate_environmental_impact(
        self,
        material_code: str,
    ) -> float:
        mat = self._get_material(material_code)
        return float(mat.get("environmental_impact", 0.5))

    def calculate_cost(
        self,
        material_code: str,
        area_sqm: float,
        penetration_depth: float,
    ) -> float:
        mat = self._get_material(material_code)
        cost_range = mat.get("cost_per_sqm_range", [200, 400])
        if len(cost_range) < 2:
            cost_per_sqm = float(cost_range[0]) if cost_range else 300.0
        else:
            min_cost, max_cost = cost_range[0], cost_range[1]
            depth_norm = (penetration_depth - 1.0) / 49.0
            depth_norm = max(0.0, min(1.0, depth_norm))
            cost_per_sqm = min_cost + depth_norm * (max_cost - min_cost)
        return float(cost_per_sqm * area_sqm)

    def calculate_reversibility(
        self,
        material_code: str,
    ) -> float:
        mat = self._get_material(material_code)
        score = mat.get("reversibility_score", 3)
        return float(score / 5.0)

    def calculate_appearance_match(
        self,
        material_code: str,
    ) -> float:
        mat = self._get_material(material_code)
        return float(mat.get("appearance_match", 0.8))

    def generate_reinforcement_plans(
        self,
        segment_id: Any,
        area_sqm: float,
        hardness: float,
        moisture: float,
        severity: str = "medium",
    ) -> List[Dict[str, Any]]:
        material_codes = list(self.materials.keys())
        if not material_codes:
            material_codes = ["TEOS-01", "TEOS-02", "GLU-01", "GLU-02", "COM-01"]

        sev_cfg = self.severity_map.get(severity, self.severity_map.get("medium", {}))
        depth_mult = sev_cfg.get("depth_multiplier", 1.0)

        plans = []
        plan_idx = 0

        for code in material_codes:
            mat = self._get_material(code)
            mat_name = mat.get("name_zh", mat.get("name", code))

            ratios = [
                ("100%", f"{mat_name}纯剂方案"),
                ("75%+25%", f"{mat_name}75%+糯米25%复合方案"),
                ("50%+50%", f"{mat_name}50%+糯米50%复合方案"),
            ]

            for ratio_str, plan_name in ratios:
                penetration = self.calculate_penetration_depth(
                    code, ratio_str, hardness, moisture
                ) * depth_mult

                durability_data = self.calculate_durability_with_confidence(code, penetration)
                env_impact = self.calculate_environmental_impact(code)
                cost_val = self.calculate_cost(code, area_sqm, penetration)
                cost_per_sqm = cost_val / max(area_sqm, 1e-6)
                reversibility = self.calculate_reversibility(code)
                appearance = self.calculate_appearance_match(code)
                difficulty = float(mat.get("construction_difficulty", 3))

                plans.append({
                    "id": f"plan_{segment_id}_{plan_idx}",
                    "plan_id": f"plan_{segment_id}_{plan_idx}",
                    "segment_id": segment_id,
                    "plan_name": plan_name,
                    "material_type": code,
                    "material_code": code,
                    "material_ratio": ratio_str,
                    "penetration_depth": float(round(penetration, 2)),
                    "durability_years": float(round(durability_data["years"], 1)),
                    "durability_confidence": float(round(durability_data["confidence"], 3)),
                    "durability_lower": float(round(durability_data["lower"], 1)),
                    "durability_upper": float(round(durability_data["upper"], 1)),
                    "cost_per_sqm": float(round(cost_per_sqm, 2)),
                    "total_cost": float(round(cost_val, 2)),
                    "construction_difficulty": difficulty,
                    "environmental_impact": float(round(env_impact, 3)),
                    "reversibility": float(round(reversibility, 3)),
                    "appearance_match": float(round(appearance, 3)),
                    "area_sqm": float(area_sqm),
                    "severity": severity,
                    "depth_multiplier": float(depth_mult),
                    "AF": durability_data["AF"],
                    "test_days": durability_data["test_days"],
                    "retention": durability_data["retention"],
                })
                plan_idx += 1

        return plans

    def evaluate(
        self,
        alternatives: List[Dict[str, Any]],
        criteria: List[str],
        weights: Dict[str, float],
        benefit_criteria: List[str],
        cost_criteria: List[str],
    ) -> List[Dict[str, Any]]:
        if not alternatives:
            return []

        n_alt = len(alternatives)
        n_crit = len(criteria)

        matrix = np.zeros((n_alt, n_crit))
        crit_to_idx = {c: i for i, c in enumerate(criteria)}

        for i, alt in enumerate(alternatives):
            for j, crit in enumerate(criteria):
                val = alt.get(crit, 0)
                if val is None:
                    val = 0
                matrix[i, j] = float(val)

        weight_array = np.array([weights.get(c, 1.0 / max(n_crit, 1)) for c in criteria])

        norms = np.sqrt(np.sum(matrix ** 2, axis=0))
        norms = np.where(norms == 0, 1, norms)
        normalized = matrix / norms

        weighted = normalized * weight_array

        benefit_indices = [crit_to_idx[c] for c in benefit_criteria if c in crit_to_idx]
        cost_indices = [crit_to_idx[c] for c in cost_criteria if c in crit_to_idx]

        positive_ideal = np.copy(weighted[0])
        negative_ideal = np.copy(weighted[0])
        for j in range(weighted.shape[1]):
            if j in benefit_indices:
                positive_ideal[j] = np.max(weighted[:, j])
                negative_ideal[j] = np.min(weighted[:, j])
            else:
                positive_ideal[j] = np.min(weighted[:, j])
                negative_ideal[j] = np.max(weighted[:, j])

        d_pos = np.sqrt(np.sum((weighted - positive_ideal) ** 2, axis=1))
        d_neg = np.sqrt(np.sum((weighted - negative_ideal) ** 2, axis=1))

        total = d_pos + d_neg
        total = np.where(total == 0, 1, total)
        closeness = d_neg / total

        ranked = np.argsort(-closeness)

        results = []
        for rank, idx in enumerate(ranked, 1):
            alt = alternatives[idx]
            crit_scores = {}
            for j, crit in enumerate(criteria):
                crit_scores[crit] = float(weighted[idx, j])

            results.append({
                "plan_id": alt.get("id") or alt.get("plan_id"),
                "plan_name": alt.get("plan_name"),
                "material_type": alt.get("material_type") or alt.get("material_code"),
                "topsis_score": float(closeness[idx]),
                "topsis_rank": int(rank),
                "criteria_scores": crit_scores,
                "d_positive": float(d_pos[idx]),
                "d_negative": float(d_neg[idx]),
                "is_selected": rank == 1,
            })

        return results

    async def handle_topsis_request(
        self,
        payload: Dict[str, Any],
        cid: str,
    ):
        try:
            mode = payload.get("mode", "generate")
            result = {}

            if mode == "evaluate":
                alternatives = payload.get("alternatives", [])
                criteria = payload.get("criteria") or self.criteria_defaults.get("weights", {}).keys()
                criteria = list(criteria)
                weights = payload.get("weights") or self.criteria_defaults.get("weights", {})
                benefit_criteria = payload.get("benefit_criteria") or self.criteria_defaults.get("benefit_criteria", [])
                cost_criteria = payload.get("cost_criteria") or self.criteria_defaults.get("cost_criteria", [])
                result = {
                    "rankings": self.evaluate(alternatives, criteria, weights, benefit_criteria, cost_criteria)
                }

            elif mode == "generate":
                segment_id = payload.get("segment_id")
                area_sqm = payload.get("area_sqm", 10.0)
                hardness = payload.get("hardness", 2.5)
                moisture = payload.get("moisture", 5.0)
                severity = payload.get("severity", "medium")
                plans = self.generate_reinforcement_plans(segment_id, area_sqm, hardness, moisture, severity)

                auto_evaluate = payload.get("auto_evaluate", True)
                if auto_evaluate and plans:
                    criteria = list(self.criteria_defaults.get("weights", {}).keys())
                    weights = self.criteria_defaults.get("weights", {})
                    benefit = self.criteria_defaults.get("benefit_criteria", [])
                    cost = self.criteria_defaults.get("cost_criteria", [])
                    rankings = self.evaluate(plans, criteria, weights, benefit, cost)
                    result = {"plans": plans, "rankings": rankings}
                else:
                    result = {"plans": plans}

            elif mode == "penetration":
                material_code = payload.get("material_code", "TEOS-01")
                material_ratio = payload.get("material_ratio", "100%")
                surface_hardness = payload.get("surface_hardness", 2.5)
                soil_moisture = payload.get("soil_moisture", 5.0)
                application_pressure = payload.get("application_pressure", 0.5)
                depth = self.calculate_penetration_depth(
                    material_code, material_ratio, surface_hardness, soil_moisture, application_pressure
                )
                durability = self.calculate_durability_with_confidence(material_code, depth)
                result = {"penetration_depth": depth, "durability": durability}

            elif mode == "durability":
                material_code = payload.get("material_code", "TEOS-01")
                penetration_depth = payload.get("penetration_depth", 10.0)
                result = self.calculate_durability_with_confidence(material_code, penetration_depth)

            elif mode == "aging_simulation":
                material_code = payload.get("material_code", "TEOS-01")
                test_T = payload.get("test_temperature")
                test_RH = payload.get("test_humidity")
                test_days = payload.get("test_days")
                result = {
                    "simulation_data": self.run_accelerated_aging_simulation(
                        material_code, test_T, test_RH, test_days
                    )
                }

            else:
                result = {"error": f"Unknown mode: {mode}"}

            if self.bus:
                await self.bus.publish(
                    RedisMessageBus.CHANNELS["TOPSIS_RESULT"],
                    {"ok": True, "mode": mode, "result": result},
                    correlation_id=cid,
                )
        except Exception as e:
            logger.error(f"Reinforcement optimizer error: {e}", exc_info=True)
            if self.bus:
                await self.bus.publish(
                    RedisMessageBus.CHANNELS["TOPSIS_RESULT"],
                    {"ok": False, "error": str(e), "mode": payload.get("mode")},
                    correlation_id=cid,
                )


_optimizer: Optional[ReinforcementOptimizerService] = None


def get_optimizer() -> ReinforcementOptimizerService:
    global _optimizer
    if _optimizer is None:
        _optimizer = ReinforcementOptimizerService()
    return _optimizer


async def start_reinforcement_optimizer_service():
    logging.basicConfig(level=logging.INFO)
    bus = await get_message_bus()
    svc = ReinforcementOptimizerService(bus=bus)
    await bus.subscribe(
        RedisMessageBus.CHANNELS["TOPSIS_REQUEST"],
        svc.handle_topsis_request,
    )
    logger.info("Reinforcement Optimizer microservice started")
    logger.info(f"Subscribed: opt:topsis:request")
    while True:
        await asyncio.sleep(60)


if __name__ == "__main__":
    asyncio.run(start_reinforcement_optimizer_service())
