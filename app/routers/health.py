from fastapi import APIRouter

from app.core.redis import check_redis_health
from app.schemas.health import HealthResponse, ReadinessResponse


router = APIRouter(prefix="/health", tags=["health"])


@router.get("/live", response_model=HealthResponse)
async def liveness_probe() -> HealthResponse:
    return HealthResponse(status="ok")


@router.get("/ready", response_model=ReadinessResponse)
async def readiness_probe() -> ReadinessResponse:
    redis_ok = await check_redis_health()
    status = "ok" if redis_ok else "degraded"
    return ReadinessResponse(status=status, redis=redis_ok)
