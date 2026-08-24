from typing import Annotated

from fastapi import APIRouter, Depends
from pydantic import BaseModel
from sqlalchemy.orm import Session

from app.core.redis import redis_client
from app.db.database import check_db_health
from app.dependencies import get_db

router = APIRouter(tags=["Healthcheck"])


class ServiceStatus(BaseModel):
    status: str  # "ok" | "degraded" | "unavailable"
    detail: str = ""


class HealthCheckResponse(BaseModel):
    status: str  # "healthy" | "degraded" | "unhealthy"
    services: dict[str, ServiceStatus]


@router.get("", response_model=HealthCheckResponse)
async def health_check(db: Annotated[Session, Depends(get_db)]):
    """
    Deep health check.

    Returns per-service status for the database, Redis, and Elasticsearch.
    Overall status is 'healthy' only when all services are 'ok'.
    """
    services: dict[str, ServiceStatus] = {}

    # Database
    try:
        db_ok = check_db_health(db)
        services["database"] = ServiceStatus(
            status="ok" if db_ok else "unavailable",
            detail="" if db_ok else "Database query failed",
        )
    except Exception as exc:
        services["database"] = ServiceStatus(status="unavailable", detail=str(exc))

    # Redis
    try:
        await redis_client.client.ping()
        services["redis"] = ServiceStatus(status="ok")
    except Exception as exc:
        services["redis"] = ServiceStatus(status="unavailable", detail=str(exc))

    # Elasticsearch (optional — app runs without it)
    try:
        from app.core.elastic_config import get_es_client

        es = await get_es_client()
        info = await es.ping()
        services["elasticsearch"] = ServiceStatus(
            status="ok" if info else "degraded",
            detail="" if info else "Ping returned False",
        )
    except Exception as exc:
        services["elasticsearch"] = ServiceStatus(
            status="degraded", detail=str(exc)
        )

    all_ok = all(s.status == "ok" for s in services.values())
    any_unavailable = any(s.status == "unavailable" for s in services.values())
    overall = "healthy" if all_ok else ("unhealthy" if any_unavailable else "degraded")

    return HealthCheckResponse(status=overall, services=services)

