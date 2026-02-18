"""Recommendation routes - List, detail, decision trail, bulk actions, approve, reject, snooze."""

import uuid
from datetime import datetime, timedelta, timezone
from enum import Enum

import structlog
from fastapi import APIRouter, Depends, HTTPException, Query, status
from pydantic import BaseModel, Field
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.middleware.auth import get_current_user, require_roles
from app.config import get_settings
from app.dependencies import get_db, get_redis
from app.integrations.hubspot.client import HubSpotClient
from app.integrations.slack.client import SlackClient
from app.models.audit_log import ActorType, AuditLog
from app.models.deal import Deal
from app.models.email_message import EmailMessage
from app.models.email_thread import EmailThread
from app.models.intent_classification import IntentClassification
from app.models.pipeline_config import PipelineConfig
from app.models.stage_recommendation import (
    RecommendationStatus,
    StageRecommendation,
    validate_transition,
)
from app.models.user_config import UserConfig, UserRole
from app.services.audit import write_audit_log
from app.services.crm_updater import execute_crm_update
from app.services.notification import update_recommendation_message
from app.utils.rate_limiter import RateLimiter

logger = structlog.get_logger()

router = APIRouter(prefix="/recommendations", tags=["Recommendations"])


# ---------- Request / Response schemas ----------


class ApproveRequest(BaseModel):
    pass


class RejectRequest(BaseModel):
    reason: str = Field(..., pattern="^(wrong_stage|wrong_deal|not_relevant|other)$")
    corrected_stage: str | None = None


class SnoozeRequest(BaseModel):
    duration_hours: int = Field(default=24, ge=1, le=168)


class RecommendationResponse(BaseModel):
    id: str
    deal_id: str
    current_stage: str
    recommended_stage: str
    recommended_stage_name: str
    confidence_score: float
    intent: str
    reasoning: str
    status: str
    reviewed_at: str | None = None
    reviewed_by: str | None = None
    rejection_reason: str | None = None
    user_corrected_stage: str | None = None
    snooze_count: int
    expires_at: str
    created_at: str

    class Config:
        from_attributes = True


class RecommendationListItem(BaseModel):
    id: str
    deal_id: str
    deal_name: str | None = None
    current_stage: str
    recommended_stage: str
    recommended_stage_name: str
    confidence_score: float
    intent: str
    status: str
    snooze_count: int
    expires_at: str
    created_at: str

    class Config:
        from_attributes = True


class PaginatedRecommendations(BaseModel):
    items: list[RecommendationListItem]
    total: int
    page: int
    page_size: int
    total_pages: int


class RecommendationDetail(BaseModel):
    id: str
    deal_id: str
    deal_name: str | None = None
    email_message_id: str
    thread_id: str
    current_stage: str
    recommended_stage: str
    recommended_stage_name: str
    confidence_score: float
    intent: str
    reasoning: str
    key_phrases: list[str]
    direction: str
    prompt_version: str
    llm_model: str
    llm_latency_ms: int | None = None
    status: str
    reviewed_at: str | None = None
    reviewed_by: str | None = None
    rejection_reason: str | None = None
    user_corrected_stage: str | None = None
    snooze_count: int
    expires_at: str
    created_at: str
    updated_at: str

    class Config:
        from_attributes = True


class EmailMessageSummary(BaseModel):
    id: str
    gmail_message_id: str
    from_address: str
    to_addresses: list[str]
    subject: str
    body_excerpt: str | None = None
    received_at: str
    created_at: str


class ClassificationSummary(BaseModel):
    id: str
    intent: str
    confidence_score: float
    reasoning: str
    key_phrases: list[str]
    direction: str
    created_at: str


class UserActionSummary(BaseModel):
    action: str
    actor_id: str | None = None
    before_state: dict | None = None
    after_state: dict | None = None
    created_at: str


class DecisionTrail(BaseModel):
    recommendation_id: str
    email: EmailMessageSummary | None = None
    classification: ClassificationSummary | None = None
    recommendation_created_at: str
    user_actions: list[UserActionSummary]


class BulkActionItem(BaseModel):
    recommendation_id: uuid.UUID
    action: str = Field(..., pattern="^(approve|reject)$")
    rejection_reason: str | None = None
    corrected_stage: str | None = None


class BulkActionRequest(BaseModel):
    items: list[BulkActionItem] = Field(..., min_length=1, max_length=50)


class BulkActionResult(BaseModel):
    recommendation_id: str
    action: str
    success: bool
    error: str | None = None


class BulkActionResponse(BaseModel):
    results: list[BulkActionResult]
    total_processed: int
    total_succeeded: int
    total_failed: int


class SortByField(str, Enum):
    created_at = "created_at"
    confidence_score = "confidence_score"
    expires_at = "expires_at"
    status = "status"


class SortOrder(str, Enum):
    asc = "asc"
    desc = "desc"


# ---------- Helpers ----------


async def _get_recommendation_or_404(
    db: AsyncSession, rec_id: uuid.UUID
) -> StageRecommendation:
    result = await db.execute(
        select(StageRecommendation).where(StageRecommendation.id == rec_id)
    )
    rec = result.scalar_one_or_none()
    if not rec:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Recommendation not found",
        )
    return rec


async def _get_deal(db: AsyncSession, deal_id: uuid.UUID) -> Deal:
    result = await db.execute(select(Deal).where(Deal.id == deal_id))
    deal = result.scalar_one_or_none()
    if not deal:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Deal not found",
        )
    return deal


def _to_response(rec: StageRecommendation) -> RecommendationResponse:
    return RecommendationResponse(
        id=str(rec.id),
        deal_id=str(rec.deal_id),
        current_stage=rec.current_stage,
        recommended_stage=rec.recommended_stage,
        recommended_stage_name=rec.recommended_stage_name,
        confidence_score=float(rec.confidence_score),
        intent=rec.intent,
        reasoning=rec.reasoning,
        status=rec.status.value,
        reviewed_at=rec.reviewed_at.isoformat() if rec.reviewed_at else None,
        reviewed_by=str(rec.reviewed_by) if rec.reviewed_by else None,
        rejection_reason=rec.rejection_reason,
        user_corrected_stage=rec.user_corrected_stage,
        snooze_count=rec.snooze_count,
        expires_at=rec.expires_at.isoformat(),
        created_at=rec.created_at.isoformat(),
    )


def _get_slack_client() -> SlackClient:
    settings = get_settings()
    return SlackClient(
        bot_token=settings.slack_bot_token,
        signing_secret=settings.slack_signing_secret,
    )


async def _get_hubspot_client() -> HubSpotClient:
    settings = get_settings()
    redis = await get_redis()
    rate_limiter = RateLimiter(redis, key_prefix="hubspot", max_tokens=8, window_seconds=1)
    return HubSpotClient(access_token=settings.hubspot_access_token, rate_limiter=rate_limiter)


# ---------- List / Detail / Trail / Bulk routes ----------


@router.get("", response_model=PaginatedRecommendations)
async def list_recommendations(
    page: int = Query(1, ge=1, description="Page number"),
    page_size: int = Query(20, ge=1, le=100, description="Items per page"),
    status_filter: RecommendationStatus | None = Query(None, alias="status", description="Filter by status"),
    deal_id: uuid.UUID | None = Query(None, description="Filter by deal ID"),
    min_confidence: float | None = Query(None, ge=0.0, le=1.0, description="Minimum confidence score"),
    max_confidence: float | None = Query(None, ge=0.0, le=1.0, description="Maximum confidence score"),
    created_after: datetime | None = Query(None, description="Filter created after (ISO 8601)"),
    created_before: datetime | None = Query(None, description="Filter created before (ISO 8601)"),
    sort_by: SortByField = Query(SortByField.created_at, description="Sort field"),
    sort_order: SortOrder = Query(SortOrder.desc, description="Sort direction"),
    db: AsyncSession = Depends(get_db),
    current_user: UserConfig = Depends(get_current_user),
) -> PaginatedRecommendations:
    """List recommendations with pagination and filters.

    Sales users see only recommendations for their own deals.
    RevOps and admin users see all recommendations.
    """
    query = select(StageRecommendation, Deal.deal_name).join(
        Deal, StageRecommendation.deal_id == Deal.id, isouter=True
    )

    # Role-based filtering: sales users only see their own deals
    if current_user.role == UserRole.SALES_USER:
        query = query.where(Deal.owner_user_id == current_user.id)

    # Apply filters
    if status_filter is not None:
        query = query.where(StageRecommendation.status == status_filter)
    if deal_id is not None:
        query = query.where(StageRecommendation.deal_id == deal_id)
    if min_confidence is not None:
        query = query.where(StageRecommendation.confidence_score >= min_confidence)
    if max_confidence is not None:
        query = query.where(StageRecommendation.confidence_score <= max_confidence)
    if created_after is not None:
        query = query.where(StageRecommendation.created_at >= created_after)
    if created_before is not None:
        query = query.where(StageRecommendation.created_at <= created_before)

    # Count total before pagination
    count_query = select(func.count()).select_from(query.subquery())
    total_result = await db.execute(count_query)
    total = total_result.scalar_one()

    # Apply sorting
    sort_column = getattr(StageRecommendation, sort_by.value)
    if sort_order == SortOrder.desc:
        query = query.order_by(sort_column.desc())
    else:
        query = query.order_by(sort_column.asc())

    # Apply pagination
    offset = (page - 1) * page_size
    query = query.offset(offset).limit(page_size)

    result = await db.execute(query)
    rows = result.all()

    items = [
        RecommendationListItem(
            id=str(rec.id),
            deal_id=str(rec.deal_id),
            deal_name=deal_name,
            current_stage=rec.current_stage,
            recommended_stage=rec.recommended_stage,
            recommended_stage_name=rec.recommended_stage_name,
            confidence_score=float(rec.confidence_score),
            intent=rec.intent,
            status=rec.status.value,
            snooze_count=rec.snooze_count,
            expires_at=rec.expires_at.isoformat(),
            created_at=rec.created_at.isoformat(),
        )
        for rec, deal_name in rows
    ]

    total_pages = (total + page_size - 1) // page_size if total > 0 else 0

    await logger.ainfo(
        "recommendations_listed",
        total=total,
        page=page,
        page_size=page_size,
        actor=current_user.email,
    )

    return PaginatedRecommendations(
        items=items,
        total=total,
        page=page,
        page_size=page_size,
        total_pages=total_pages,
    )


@router.get("/{recommendation_id}", response_model=RecommendationDetail)
async def get_recommendation(
    recommendation_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    current_user: UserConfig = Depends(get_current_user),
) -> RecommendationDetail:
    """Get a single recommendation with full details."""
    query = (
        select(StageRecommendation, Deal.deal_name)
        .join(Deal, StageRecommendation.deal_id == Deal.id, isouter=True)
        .where(StageRecommendation.id == recommendation_id)
    )

    # Sales users can only view their own deals' recommendations
    if current_user.role == UserRole.SALES_USER:
        query = query.where(Deal.owner_user_id == current_user.id)

    result = await db.execute(query)
    row = result.one_or_none()

    if not row:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Recommendation not found",
        )

    rec, deal_name = row

    await logger.ainfo(
        "recommendation_detail_viewed",
        recommendation_id=str(rec.id),
        actor=current_user.email,
    )

    return RecommendationDetail(
        id=str(rec.id),
        deal_id=str(rec.deal_id),
        deal_name=deal_name,
        email_message_id=str(rec.email_message_id),
        thread_id=str(rec.thread_id),
        current_stage=rec.current_stage,
        recommended_stage=rec.recommended_stage,
        recommended_stage_name=rec.recommended_stage_name,
        confidence_score=float(rec.confidence_score),
        intent=rec.intent,
        reasoning=rec.reasoning,
        key_phrases=rec.key_phrases or [],
        direction=rec.direction.value,
        prompt_version=rec.prompt_version,
        llm_model=rec.llm_model,
        llm_latency_ms=rec.llm_latency_ms,
        status=rec.status.value,
        reviewed_at=rec.reviewed_at.isoformat() if rec.reviewed_at else None,
        reviewed_by=str(rec.reviewed_by) if rec.reviewed_by else None,
        rejection_reason=rec.rejection_reason,
        user_corrected_stage=rec.user_corrected_stage,
        snooze_count=rec.snooze_count,
        expires_at=rec.expires_at.isoformat(),
        created_at=rec.created_at.isoformat(),
        updated_at=rec.updated_at.isoformat(),
    )


@router.get("/{recommendation_id}/trail", response_model=DecisionTrail)
async def get_decision_trail(
    recommendation_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    current_user: UserConfig = Depends(get_current_user),
) -> DecisionTrail:
    """Get the decision trail for a recommendation.

    Traces the full chain: email message -> intent classification -> recommendation -> user actions.
    """
    rec = await _get_recommendation_or_404(db, recommendation_id)

    # For sales users, verify they own the deal
    if current_user.role == UserRole.SALES_USER:
        deal_result = await db.execute(
            select(Deal).where(
                Deal.id == rec.deal_id,
                Deal.owner_user_id == current_user.id,
            )
        )
        if not deal_result.scalar_one_or_none():
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Recommendation not found",
            )

    # Fetch the email message
    email_summary = None
    email_result = await db.execute(
        select(EmailMessage).where(EmailMessage.id == rec.email_message_id)
    )
    email_msg = email_result.scalar_one_or_none()
    if email_msg:
        email_summary = EmailMessageSummary(
            id=str(email_msg.id),
            gmail_message_id=email_msg.gmail_message_id,
            from_address=email_msg.from_address,
            to_addresses=email_msg.to_addresses or [],
            subject=email_msg.subject,
            body_excerpt=email_msg.body_excerpt,
            received_at=email_msg.received_at.isoformat(),
            created_at=email_msg.created_at.isoformat(),
        )

    # Fetch the intent classification for this email + deal
    classification_summary = None
    classification_result = await db.execute(
        select(IntentClassification).where(
            IntentClassification.email_message_id == rec.email_message_id,
            IntentClassification.deal_id == rec.deal_id,
        ).order_by(IntentClassification.created_at.desc()).limit(1)
    )
    classification = classification_result.scalar_one_or_none()
    if classification:
        classification_summary = ClassificationSummary(
            id=str(classification.id),
            intent=classification.intent,
            confidence_score=float(classification.confidence_score),
            reasoning=classification.reasoning,
            key_phrases=classification.key_phrases or [],
            direction=classification.direction.value,
            created_at=classification.created_at.isoformat(),
        )

    # Fetch audit log entries for this recommendation
    audit_result = await db.execute(
        select(AuditLog).where(
            AuditLog.entity_type == "stage_recommendation",
            AuditLog.entity_id == rec.id,
        ).order_by(AuditLog.created_at.asc())
    )
    audit_entries = audit_result.scalars().all()

    user_actions = [
        UserActionSummary(
            action=entry.action,
            actor_id=entry.actor_id,
            before_state=entry.before_state,
            after_state=entry.after_state,
            created_at=entry.created_at.isoformat(),
        )
        for entry in audit_entries
    ]

    await logger.ainfo(
        "decision_trail_viewed",
        recommendation_id=str(rec.id),
        actor=current_user.email,
    )

    return DecisionTrail(
        recommendation_id=str(rec.id),
        email=email_summary,
        classification=classification_summary,
        recommendation_created_at=rec.created_at.isoformat(),
        user_actions=user_actions,
    )


@router.post("/bulk", response_model=BulkActionResponse)
async def bulk_action(
    body: BulkActionRequest,
    db: AsyncSession = Depends(get_db),
    current_user: UserConfig = Depends(require_roles(UserRole.ADMIN, UserRole.REVOPS)),
) -> BulkActionResponse:
    """Bulk approve or reject recommendations. Requires revops or admin role."""
    results: list[BulkActionResult] = []
    succeeded = 0
    failed = 0

    for item in body.items:
        try:
            rec_result = await db.execute(
                select(StageRecommendation).where(
                    StageRecommendation.id == item.recommendation_id
                )
            )
            rec = rec_result.scalar_one_or_none()

            if not rec:
                results.append(BulkActionResult(
                    recommendation_id=str(item.recommendation_id),
                    action=item.action,
                    success=False,
                    error="Recommendation not found",
                ))
                failed += 1
                continue

            if item.action == "approve":
                if not validate_transition(rec.status, RecommendationStatus.APPROVED):
                    results.append(BulkActionResult(
                        recommendation_id=str(item.recommendation_id),
                        action=item.action,
                        success=False,
                        error=f"Cannot approve: status is '{rec.status.value}'",
                    ))
                    failed += 1
                    continue

                deal = await _get_deal(db, rec.deal_id)

                rec.status = RecommendationStatus.APPROVED
                rec.reviewed_at = datetime.now(timezone.utc)
                rec.reviewed_by = current_user.id
                await db.flush()

                await write_audit_log(
                    db,
                    action="recommendation_approved",
                    entity_type="stage_recommendation",
                    entity_id=rec.id,
                    actor_type=ActorType.USER,
                    actor_id=str(current_user.id),
                    before_state={"status": "pending"},
                    after_state={"status": "approved", "bulk": True},
                )

                # Execute CRM update
                hubspot_client = await _get_hubspot_client()
                await execute_crm_update(
                    db, hubspot_client, rec, deal,
                    actor_id=str(current_user.id),
                )

                results.append(BulkActionResult(
                    recommendation_id=str(item.recommendation_id),
                    action=item.action,
                    success=True,
                ))
                succeeded += 1

            elif item.action == "reject":
                if not validate_transition(rec.status, RecommendationStatus.REJECTED):
                    results.append(BulkActionResult(
                        recommendation_id=str(item.recommendation_id),
                        action=item.action,
                        success=False,
                        error=f"Cannot reject: status is '{rec.status.value}'",
                    ))
                    failed += 1
                    continue

                before_state = {"status": rec.status.value}
                rec.status = RecommendationStatus.REJECTED
                rec.reviewed_at = datetime.now(timezone.utc)
                rec.reviewed_by = current_user.id
                rec.rejection_reason = item.rejection_reason
                rec.user_corrected_stage = item.corrected_stage
                await db.flush()

                await write_audit_log(
                    db,
                    action="recommendation_rejected",
                    entity_type="stage_recommendation",
                    entity_id=rec.id,
                    actor_type=ActorType.USER,
                    actor_id=str(current_user.id),
                    before_state=before_state,
                    after_state={
                        "status": "rejected",
                        "reason": item.rejection_reason,
                        "corrected_stage": item.corrected_stage,
                        "bulk": True,
                    },
                )

                results.append(BulkActionResult(
                    recommendation_id=str(item.recommendation_id),
                    action=item.action,
                    success=True,
                ))
                succeeded += 1

        except Exception as exc:
            await logger.aerror(
                "bulk_action_item_failed",
                recommendation_id=str(item.recommendation_id),
                action=item.action,
                error=str(exc),
            )
            results.append(BulkActionResult(
                recommendation_id=str(item.recommendation_id),
                action=item.action,
                success=False,
                error="Internal processing error",
            ))
            failed += 1

    await logger.ainfo(
        "bulk_action_completed",
        total=len(body.items),
        succeeded=succeeded,
        failed=failed,
        actor=current_user.email,
    )

    return BulkActionResponse(
        results=results,
        total_processed=len(body.items),
        total_succeeded=succeeded,
        total_failed=failed,
    )


# ---------- Action routes (approve / reject / snooze) ----------


@router.post("/{recommendation_id}/approve", response_model=RecommendationResponse)
async def approve_recommendation(
    recommendation_id: uuid.UUID,
    body: ApproveRequest | None = None,
    db: AsyncSession = Depends(get_db),
    current_user: UserConfig = Depends(get_current_user),
) -> RecommendationResponse:
    """Approve a recommendation and trigger CRM stage update."""
    rec = await _get_recommendation_or_404(db, recommendation_id)

    if not validate_transition(rec.status, RecommendationStatus.APPROVED):
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=f"Cannot approve: recommendation is '{rec.status.value}', expected 'pending'",
        )

    deal = await _get_deal(db, rec.deal_id)

    # Transition to approved
    rec.status = RecommendationStatus.APPROVED
    rec.reviewed_at = datetime.now(timezone.utc)
    rec.reviewed_by = current_user.id
    await db.flush()

    await write_audit_log(
        db,
        action="recommendation_approved",
        entity_type="stage_recommendation",
        entity_id=rec.id,
        actor_type=ActorType.USER,
        actor_id=str(current_user.id),
        before_state={"status": "pending"},
        after_state={"status": "approved"},
    )

    # Execute CRM update
    hubspot_client = await _get_hubspot_client()
    crm_result = await execute_crm_update(
        db, hubspot_client, rec, deal,
        actor_id=str(current_user.id),
    )

    # Update Slack message
    slack_client = _get_slack_client()
    status_text = "Approved" if crm_result.success else f"Approved (CRM: {crm_result.status.value})"
    await update_recommendation_message(
        slack_client, rec, deal,
        action_text=status_text,
        actor_name=current_user.display_name,
    )

    await logger.ainfo(
        "recommendation_approved",
        recommendation_id=str(rec.id),
        crm_success=crm_result.success,
        actor=current_user.email,
    )

    return _to_response(rec)


@router.post("/{recommendation_id}/reject", response_model=RecommendationResponse)
async def reject_recommendation(
    recommendation_id: uuid.UUID,
    body: RejectRequest,
    db: AsyncSession = Depends(get_db),
    current_user: UserConfig = Depends(get_current_user),
) -> RecommendationResponse:
    """Reject a recommendation with reason and optional corrected stage."""
    rec = await _get_recommendation_or_404(db, recommendation_id)

    if not validate_transition(rec.status, RecommendationStatus.REJECTED):
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=f"Cannot reject: recommendation is '{rec.status.value}', expected 'pending'",
        )

    deal = await _get_deal(db, rec.deal_id)

    before_state = {"status": rec.status.value}
    rec.status = RecommendationStatus.REJECTED
    rec.reviewed_at = datetime.now(timezone.utc)
    rec.reviewed_by = current_user.id
    rec.rejection_reason = body.reason
    rec.user_corrected_stage = body.corrected_stage
    await db.flush()

    await write_audit_log(
        db,
        action="recommendation_rejected",
        entity_type="stage_recommendation",
        entity_id=rec.id,
        actor_type=ActorType.USER,
        actor_id=str(current_user.id),
        before_state=before_state,
        after_state={
            "status": "rejected",
            "reason": body.reason,
            "corrected_stage": body.corrected_stage,
        },
    )

    # If user provided a corrected stage, write that to CRM instead
    if body.corrected_stage:
        hubspot_client = await _get_hubspot_client()
        note = (
            f"[Pipeline Intelligence] Manual correction by {current_user.display_name}: "
            f"Rejected AI suggestion ({rec.recommended_stage_name}), "
            f"manually set to stage {body.corrected_stage}"
        )
        try:
            await hubspot_client.update_deal_stage(
                deal_id=deal.hubspot_deal_id,
                stage_id=body.corrected_stage,
                note=note,
            )
        except Exception as exc:
            await logger.aerror(
                "corrected_stage_crm_write_failed",
                error=str(exc),
                recommendation_id=str(rec.id),
            )

    # Update Slack message
    slack_client = _get_slack_client()
    await update_recommendation_message(
        slack_client, rec, deal,
        action_text=f"Rejected ({body.reason})",
        actor_name=current_user.display_name,
    )

    await logger.ainfo(
        "recommendation_rejected",
        recommendation_id=str(rec.id),
        reason=body.reason,
        actor=current_user.email,
    )

    return _to_response(rec)


@router.post("/{recommendation_id}/snooze", response_model=RecommendationResponse)
async def snooze_recommendation(
    recommendation_id: uuid.UUID,
    body: SnoozeRequest | None = None,
    db: AsyncSession = Depends(get_db),
    current_user: UserConfig = Depends(get_current_user),
) -> RecommendationResponse:
    """Snooze a recommendation for later review."""
    rec = await _get_recommendation_or_404(db, recommendation_id)

    if not validate_transition(rec.status, RecommendationStatus.SNOOZED):
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=f"Cannot snooze: recommendation is '{rec.status.value}'",
        )

    # Check max snoozes from pipeline config
    pipeline_result = await db.execute(
        select(PipelineConfig).where(
            PipelineConfig.hubspot_pipeline_id == (
                select(Deal.hubspot_pipeline_id)
                .where(Deal.id == rec.deal_id)
                .correlate(None)
                .scalar_subquery()
            ),
            PipelineConfig.is_active.is_(True),
        )
    )
    pipeline_config = pipeline_result.scalar_one_or_none()
    max_snoozes = pipeline_config.max_snoozes if pipeline_config else 2

    if rec.snooze_count >= max_snoozes:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=f"Max snoozes ({max_snoozes}) reached",
        )

    deal = await _get_deal(db, rec.deal_id)

    duration = body.duration_hours if body else 24
    rec.status = RecommendationStatus.SNOOZED
    rec.snooze_count += 1
    rec.expires_at = datetime.now(timezone.utc) + timedelta(hours=duration)
    await db.flush()

    await write_audit_log(
        db,
        action="recommendation_snoozed",
        entity_type="stage_recommendation",
        entity_id=rec.id,
        actor_type=ActorType.USER,
        actor_id=str(current_user.id),
        after_state={
            "status": "snoozed",
            "snooze_count": rec.snooze_count,
            "new_expires_at": rec.expires_at.isoformat(),
        },
    )

    # Update Slack message
    slack_client = _get_slack_client()
    await update_recommendation_message(
        slack_client, rec, deal,
        action_text=f"Snoozed ({duration}h)",
        actor_name=current_user.display_name,
    )

    await logger.ainfo(
        "recommendation_snoozed",
        recommendation_id=str(rec.id),
        snooze_count=rec.snooze_count,
        duration_hours=duration,
        actor=current_user.email,
    )

    return _to_response(rec)
