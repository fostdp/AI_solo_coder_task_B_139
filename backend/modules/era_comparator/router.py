from fastapi import APIRouter, HTTPException
from .schemas import CrossEraComparisonRequest, CrossEraComparisonResponse
from .service import era_comparison_service

router = APIRouter(prefix="/api/cross-era", tags=["Era Comparator"])


@router.post("/compare", response_model=CrossEraComparisonResponse)
async def compare_cross_era(request: CrossEraComparisonRequest):
    try:
        result = era_comparison_service.compare_cross_era(
            request.include_dynasties,
            request.include_modern,
            request.wind_speed,
            request.soil_moisture
        )
        return result
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
