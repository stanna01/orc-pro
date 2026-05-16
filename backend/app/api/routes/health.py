from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, ConfigDict
from datetime import datetime, timezone
from typing import Literal
import logging

from backend.app.config import get_settings

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/health", tags=["health"])


class HealthResponse(BaseModel):
    status: Literal["healthy", "degraded", "unhealthy"]
    timestamp: datetime
    version: str
    environment: str

    model_config = ConfigDict(
        json_schema_extra={
            "example": {
                "status": "healthy",
                "timestamp": "2026-04-04T12:00:00Z",
                "version": "0.1.0",
                "environment": "development",
            }
        }
    )


@router.get(
    "/",
    response_model=HealthResponse,
    summary="Health Check",
    description="Returns application health status. Used by load balancers and monitoring systems.",
)
async def health_check() -> HealthResponse:
    settings = get_settings()
    try:
        status = "healthy"
        response = HealthResponse(
            status=status,
            timestamp=datetime.now(timezone.utc),
            version=settings.app_version,
            environment=settings.environment,
        )
        logger.debug(f"Health check passed: {response.status}")
        return response
    except Exception as e:
        logger.error(f"Health check failed: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail="Application health check failed")


@router.get(
    "/ready",
    response_model=dict,
    summary="Readiness Check",
    description="Returns 200 if the application is ready to handle requests. Used for deployment readiness.",
)
async def readiness_check() -> dict:
    try:
        logger.debug("Readiness check passed")
        return {"ready": True, "timestamp": datetime.now(timezone.utc).isoformat()}
    except Exception as e:
        logger.error(f"Readiness check failed: {e}", exc_info=True)
        raise HTTPException(status_code=503, detail="Application is not ready")


@router.get(
    "/live",
    response_model=dict,
    summary="Liveness Check",
    description="Returns 200 if the application is alive. Used for crash detection.",
)
async def liveness_check() -> dict:
    logger.debug("Liveness check passed")
    return {"alive": True, "timestamp": datetime.now(timezone.utc).isoformat()}
