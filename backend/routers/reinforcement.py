from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from typing import List
from datetime import datetime
from ..database import get_db
from ..models.orm import ReinforcementPlan, ReinforcementMaterial, WallSegment
from ..models.schemas import (
    ReinforcementPlan as ReinforcementPlanSchema,
    ReinforcementPlanCreate,
    TOPSISEvaluationRequest,
    TOPSISEvaluationResult
)
from ..services.topsis_optimizer import topsis_evaluator

router = APIRouter(prefix="/api/reinforcement", tags=["Reinforcement Plans"])


@router.get("/materials")
async def get_reinforcement_materials(db: AsyncSession = Depends(get_db)):
    stmt = select(ReinforcementMaterial).order_by(ReinforcementMaterial.id)
    result = await db.execute(stmt)
    return result.scalars().all()


@router.get("/plans", response_model=List[ReinforcementPlanSchema])
async def get_reinforcement_plans(
    segment_id: int = None,
    db: AsyncSession = Depends(get_db)
):
    stmt = select(ReinforcementPlan)
    
    if segment_id is not None:
        stmt = stmt.where(ReinforcementPlan.segment_id == segment_id)
    
    stmt = stmt.order_by(ReinforcementPlan.created_at.desc())
    result = await db.execute(stmt)
    return result.scalars().all()


@router.get("/plans/{plan_id}", response_model=ReinforcementPlanSchema)
async def get_reinforcement_plan(plan_id: int, db: AsyncSession = Depends(get_db)):
    plan = await db.get(ReinforcementPlan, plan_id)
    if not plan:
        raise HTTPException(status_code=404, detail="Reinforcement plan not found")
    return plan


@router.post("/plans", response_model=ReinforcementPlanSchema)
async def create_reinforcement_plan(
    plan: ReinforcementPlanCreate,
    db: AsyncSession = Depends(get_db)
):
    segment = await db.get(WallSegment, plan.segment_id)
    if not segment:
        raise HTTPException(status_code=404, detail="Wall segment not found")
    
    db_plan = ReinforcementPlan(**plan.model_dump())
    db.add(db_plan)
    await db.commit()
    await db.refresh(db_plan)
    return db_plan


@router.post("/plans/generate")
async def generate_reinforcement_plans(
    segment_id: int,
    erosion_severity: str = "medium",
    db: AsyncSession = Depends(get_db)
):
    segment = await db.get(WallSegment, segment_id)
    if not segment:
        raise HTTPException(status_code=404, detail="Wall segment not found")
    
    area = segment.length_m * segment.height_m
    
    from sqlalchemy import select, func
    from ..models.orm import SensorData
    
    stmt = (
        select(
            func.avg(SensorData.surface_hardness).label("avg_hardness"),
            func.avg(SensorData.soil_moisture).label("avg_moisture")
        )
        .where(SensorData.segment_id == segment_id)
    )
    result = await db.execute(stmt)
    row = result.first()
    
    avg_hardness = float(row.avg_hardness or 2.5)
    avg_moisture = float(row.avg_moisture or 5.0)
    
    plans = topsis_evaluator.generate_reinforcement_plans(
        segment_id, area, avg_hardness, avg_moisture, erosion_severity
    )
    
    created_plans = []
    for p in plans:
        db_plan = ReinforcementPlan(**p)
        db.add(db_plan)
        created_plans.append(db_plan)
    
    await db.commit()
    for plan in created_plans:
        await db.refresh(plan)
    
    return {
        "segment_id": segment_id,
        "segment_name": segment.name,
        "area_sqm": area,
        "avg_hardness": avg_hardness,
        "avg_moisture": avg_moisture,
        "erosion_severity": erosion_severity,
        "plans": created_plans
    }


@router.post("/evaluate", response_model=List[TOPSISEvaluationResult])
async def evaluate_reinforcement_plans(
    request: TOPSISEvaluationRequest,
    db: AsyncSession = Depends(get_db)
):
    try:
        results = await topsis_evaluator.evaluate_segment_plans(db, request)
        return results
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/calculate-penetration")
async def calculate_penetration_depth(
    material_code: str,
    surface_hardness: float,
    soil_moisture: float,
    material_ratio: str = "100%",
    application_pressure: float = 0.5
):
    depth = topsis_evaluator.calculate_penetration_depth(
        material_code, material_ratio, surface_hardness, soil_moisture, application_pressure
    )
    
    durability = topsis_evaluator.calculate_durability(material_code, depth)
    env_impact = topsis_evaluator.calculate_environmental_impact(material_code)
    
    return {
        "material_code": material_code,
        "penetration_depth_mm": round(depth, 2),
        "estimated_durability_years": round(durability, 1),
        "environmental_impact_index": round(env_impact, 3)
    }


@router.post("/select-plan")
async def select_reinforcement_plan(
    plan_id: int,
    db: AsyncSession = Depends(get_db)
):
    plan = await db.get(ReinforcementPlan, plan_id)
    if not plan:
        raise HTTPException(status_code=404, detail="Reinforcement plan not found")
    
    stmt = select(ReinforcementPlan).where(
        ReinforcementPlan.segment_id == plan.segment_id
    )
    result = await db.execute(stmt)
    all_plans = result.scalars().all()
    
    for p in all_plans:
        p.is_selected = (p.id == plan_id)
    
    await db.commit()
    await db.refresh(plan)
    
    return {
        "message": f"Plan {plan_id} selected successfully",
        "plan": plan
    }
