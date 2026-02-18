"""Health check, readiness probe, and Prometheus metrics routes."""

from datetime import datetime, timezone

from fastapi import APIRouter, Depends
from fastapi.responses import PlainTextResponse
from prometheus_client import (
    Counter,
    Histogram,
    Gauge,
    generate_latest,
    CONTENT_TYPE_LATEST,
)
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from app.dependencies import get_db, get_redis

router = APIRouter(tags=["Health"])

# ── Prometheus Metrics ────────────────────────────────────────

EMAIL_PROCESSING_LATENCY = Histogram(
    "email_processing_latency_seconds",
    "Time from email receipt to notification delivery",
    buckets=[1, 5, 10, 30, 60, 120, 300],
)

CLASSIFICATION_LATENCY = Histogram(
    "classification_latency_seconds",
    "LLM intent classification latency",
    buckets=[0.5, 1, 2, 5, 10, 30],
)

RECOMMENDATION_COUNT = Counter(
    "recommendations_total",
    "Total recommendations generated",
    ["status"],
)

API_REQUEST_DURATION = Histogram(
    "api_request_duration_seconds",
    "API request processing time",
    ["method", "endpoint", "status_code"],
    buckets=[0.01, 0.05, 0.1, 0.25, 0.5, 1, 2.5, 5],
)

DLQ_DEPTH = Gauge(
    "dlq_depth",
    "Current number of messages in the Redis dead letter queue",
)

ACTIVE_USERS = Gauge(
    "active_users",
    "Number of active users with Gmail watch configured",
)


# ── Health Endpoints ──────────────────────────────────────────


@router.get("/health")
async def health_check(
    db: AsyncSession = Depends(get_db),
    redis=Depends(get_redis),
) -> dict:
    """System health check - status of all dependencies."""
    checks: dict = {}
    overall = "healthy"

    # Database check
    try:
        await db.execute(text("SELECT 1"))
        checks["database"] = {"status": "ok"}
    except Exception as e:
        checks["database"] = {"status": "down", "error": str(e)}
        overall = "unhealthy"

    # Redis check
    try:
        await redis.ping()
        checks["redis"] = {"status": "ok"}
    except Exception as e:
        checks["redis"] = {"status": "down", "error": str(e)}
        overall = "unhealthy"

    return {
        "status": overall,
        "checks": checks,
        "timestamp": datetime.now(timezone.utc).isoformat(),
    }


@router.get("/health/ready")
async def readiness_check(db: AsyncSession = Depends(get_db)) -> dict:
    """Readiness probe for container orchestration."""
    try:
        await db.execute(text("SELECT 1"))
        return {"status": "ready"}
    except Exception:
        from fastapi.responses import JSONResponse

        return JSONResponse(status_code=503, content={"status": "not_ready"})


@router.get("/metrics")
async def prometheus_metrics() -> PlainTextResponse:
    """Prometheus metrics endpoint for scraping."""
    return PlainTextResponse(
        content=generate_latest().decode("utf-8"),
        media_type=CONTENT_TYPE_LATEST,
    )
