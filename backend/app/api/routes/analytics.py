"""Analytics routes - KPI overview and low-confidence review."""

import uuid
from datetime import datetime, timedelta, timezone

import structlog
from fastapi import APIRouter, Depends, Query
from pydantic import BaseModel
from sqlalchemy import case, distinct, func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.middleware.auth import require_roles
from app.dependencies import get_db
from app.models.deal import Deal
from app.models.email_message import EmailMessage
from app.models.email_thread import EmailThread
from app.models.intent_classification import IntentClassification
from app.models.stage_recommendation import RecommendationStatus, StageRecommendation
from app.models.user_config import UserConfig, UserRole

logger = structlog.get_logger()

router = APIRouter(prefix="/analytics", tags=["Analytics"])


# ---------- Response schemas ----------


class RecommendationMetrics(BaseModel):
    total: int
    approved: int
    rejected: int
    expired: int
    pending: int
    snoozed: int
    approval_rate: float


class ConfidenceMetrics(BaseModel):
    average: float | None = None
    p50: float | None = None
    p95: float | None = None


class LatencyMetrics(BaseModel):
    email_to_notification_p50_seconds: float | None = None
    email_to_notification_p95_seconds: float | None = None


class DealCoverageMetrics(BaseModel):
    total_active_deals: int
    deals_with_threads: int
    coverage_percent: float


class AnalyticsOverview(BaseModel):
    period_days: int
    recommendations: RecommendationMetrics
    rejections_by_reason: dict[str, int]
    confidence: ConfidenceMetrics
    latency: LatencyMetrics
    deal_coverage: DealCoverageMetrics


class LowConfidenceItem(BaseModel):
    id: str
    email_message_id: str
    deal_id: str | None = None
    deal_name: str | None = None
    email_subject: str | None = None
    email_excerpt: str | None = None
    intent: str
    confidence_score: float
    reasoning: str
    key_phrases: list[str]
    direction: str
    created_at: str

    class Config:
        from_attributes = True


class PaginatedLowConfidence(BaseModel):
    items: list[LowConfidenceItem]
    total: int
    page: int
    page_size: int
    total_pages: int


# ---------- Routes ----------


@router.get("/overview", response_model=AnalyticsOverview)
async def analytics_overview(
    period_days: int = Query(7, description="Period in days (7, 14, 30, 90)"),
    db: AsyncSession = Depends(get_db),
    current_user: UserConfig = Depends(require_roles(UserRole.ADMIN, UserRole.REVOPS)),
) -> AnalyticsOverview:
    """Aggregate metrics over a given period. Requires revops or admin role."""
    if period_days not in (7, 14, 30, 90):
        period_days = 7

    cutoff = datetime.now(timezone.utc) - timedelta(days=period_days)

    # --- Recommendation counts by status ---
    status_counts_result = await db.execute(
        select(
            StageRecommendation.status,
            func.count(StageRecommendation.id),
        )
        .where(StageRecommendation.created_at >= cutoff)
        .group_by(StageRecommendation.status)
    )
    status_counts: dict[str, int] = {}
    for row_status, count in status_counts_result.all():
        status_counts[row_status.value] = count

    total = sum(status_counts.values())
    approved = status_counts.get("approved", 0) + status_counts.get("write_success", 0)
    rejected = status_counts.get("rejected", 0)
    expired = status_counts.get("expired", 0)
    pending = status_counts.get("pending", 0)
    snoozed = status_counts.get("snoozed", 0)

    decisions_made = approved + rejected
    approval_rate = (approved / decisions_made * 100.0) if decisions_made > 0 else 0.0

    recommendations = RecommendationMetrics(
        total=total,
        approved=approved,
        rejected=rejected,
        expired=expired,
        pending=pending,
        snoozed=snoozed,
        approval_rate=round(approval_rate, 2),
    )

    # --- Rejections by reason ---
    rejections_result = await db.execute(
        select(
            StageRecommendation.rejection_reason,
            func.count(StageRecommendation.id),
        )
        .where(
            StageRecommendation.created_at >= cutoff,
            StageRecommendation.status == RecommendationStatus.REJECTED,
            StageRecommendation.rejection_reason.isnot(None),
        )
        .group_by(StageRecommendation.rejection_reason)
    )
    rejections_by_reason: dict[str, int] = {}
    for reason, count in rejections_result.all():
        rejections_by_reason[reason] = count

    # --- Confidence metrics ---
    # Use SQL aggregate functions. For percentiles, compute in Python for portability.
    confidence_result = await db.execute(
        select(StageRecommendation.confidence_score)
        .where(StageRecommendation.created_at >= cutoff)
        .order_by(StageRecommendation.confidence_score.asc())
    )
    confidence_values = [float(row[0]) for row in confidence_result.all()]

    if confidence_values:
        avg_confidence = sum(confidence_values) / len(confidence_values)
        p50_confidence = _percentile(confidence_values, 0.50)
        p95_confidence = _percentile(confidence_values, 0.95)
    else:
        avg_confidence = None
        p50_confidence = None
        p95_confidence = None

    confidence = ConfidenceMetrics(
        average=round(avg_confidence, 4) if avg_confidence is not None else None,
        p50=round(p50_confidence, 4) if p50_confidence is not None else None,
        p95=round(p95_confidence, 4) if p95_confidence is not None else None,
    )

    # --- Latency: email created_at to recommendation created_at ---
    latency_result = await db.execute(
        select(
            func.extract(
                "epoch",
                StageRecommendation.created_at - EmailMessage.created_at,
            ).label("latency_seconds")
        )
        .join(EmailMessage, StageRecommendation.email_message_id == EmailMessage.id)
        .where(StageRecommendation.created_at >= cutoff)
        .order_by("latency_seconds")
    )
    latency_values = [float(row[0]) for row in latency_result.all() if row[0] is not None]

    if latency_values:
        latency_p50 = _percentile(latency_values, 0.50)
        latency_p95 = _percentile(latency_values, 0.95)
    else:
        latency_p50 = None
        latency_p95 = None

    latency = LatencyMetrics(
        email_to_notification_p50_seconds=round(latency_p50, 2) if latency_p50 is not None else None,
        email_to_notification_p95_seconds=round(latency_p95, 2) if latency_p95 is not None else None,
    )

    # --- Deal coverage ---
    total_active_deals_result = await db.execute(
        select(func.count(Deal.id))
    )
    total_active_deals = total_active_deals_result.scalar_one()

    deals_with_threads_result = await db.execute(
        select(func.count(distinct(EmailThread.deal_id)))
        .where(EmailThread.deal_id.isnot(None))
    )
    deals_with_threads = deals_with_threads_result.scalar_one()

    coverage_percent = (
        (deals_with_threads / total_active_deals * 100.0)
        if total_active_deals > 0
        else 0.0
    )

    deal_coverage = DealCoverageMetrics(
        total_active_deals=total_active_deals,
        deals_with_threads=deals_with_threads,
        coverage_percent=round(coverage_percent, 2),
    )

    await logger.ainfo(
        "analytics_overview_retrieved",
        period_days=period_days,
        total_recommendations=total,
        actor=current_user.email,
    )

    return AnalyticsOverview(
        period_days=period_days,
        recommendations=recommendations,
        rejections_by_reason=rejections_by_reason,
        confidence=confidence,
        latency=latency,
        deal_coverage=deal_coverage,
    )


@router.get("/classifications/low-confidence", response_model=PaginatedLowConfidence)
async def list_low_confidence_classifications(
    page: int = Query(1, ge=1, description="Page number"),
    page_size: int = Query(20, ge=1, le=100, description="Items per page"),
    min_confidence: float = Query(0.30, ge=0.0, le=1.0, description="Minimum confidence score"),
    max_confidence: float = Query(0.70, ge=0.0, le=1.0, description="Maximum confidence score"),
    db: AsyncSession = Depends(get_db),
    current_user: UserConfig = Depends(require_roles(UserRole.ADMIN, UserRole.REVOPS)),
) -> PaginatedLowConfidence:
    """List intent classifications with confidence in a given range.

    Useful for reviewing borderline classifications that may need attention.
    Includes email subject and excerpt from joined EmailMessage, and deal name from joined Deal.
    """
    query = (
        select(
            IntentClassification,
            EmailMessage.subject.label("email_subject"),
            EmailMessage.body_excerpt.label("email_excerpt"),
            Deal.deal_name.label("deal_name"),
        )
        .join(EmailMessage, IntentClassification.email_message_id == EmailMessage.id)
        .join(Deal, IntentClassification.deal_id == Deal.id, isouter=True)
        .where(
            IntentClassification.confidence_score >= min_confidence,
            IntentClassification.confidence_score <= max_confidence,
        )
    )

    # Count total before pagination
    count_query = select(func.count()).select_from(query.subquery())
    total_result = await db.execute(count_query)
    total = total_result.scalar_one()

    # Order by confidence ascending (lowest confidence first) and paginate
    query = query.order_by(IntentClassification.confidence_score.asc())
    offset = (page - 1) * page_size
    query = query.offset(offset).limit(page_size)

    result = await db.execute(query)
    rows = result.all()

    items = [
        LowConfidenceItem(
            id=str(classification.id),
            email_message_id=str(classification.email_message_id),
            deal_id=str(classification.deal_id) if classification.deal_id else None,
            deal_name=deal_name,
            email_subject=email_subject,
            email_excerpt=email_excerpt,
            intent=classification.intent,
            confidence_score=float(classification.confidence_score),
            reasoning=classification.reasoning,
            key_phrases=classification.key_phrases or [],
            direction=classification.direction.value,
            created_at=classification.created_at.isoformat(),
        )
        for classification, email_subject, email_excerpt, deal_name in rows
    ]

    total_pages = (total + page_size - 1) // page_size if total > 0 else 0

    await logger.ainfo(
        "low_confidence_classifications_listed",
        total=total,
        page=page,
        min_confidence=min_confidence,
        max_confidence=max_confidence,
        actor=current_user.email,
    )

    return PaginatedLowConfidence(
        items=items,
        total=total,
        page=page,
        page_size=page_size,
        total_pages=total_pages,
    )


# ---------- Helpers ----------


def _percentile(sorted_values: list[float], percentile: float) -> float:
    """Compute percentile from a pre-sorted list of values using linear interpolation."""
    if not sorted_values:
        return 0.0
    n = len(sorted_values)
    if n == 1:
        return sorted_values[0]
    # Use linear interpolation (same method as numpy's default)
    index = percentile * (n - 1)
    lower = int(index)
    upper = lower + 1
    if upper >= n:
        return sorted_values[-1]
    fraction = index - lower
    return sorted_values[lower] + fraction * (sorted_values[upper] - sorted_values[lower])
