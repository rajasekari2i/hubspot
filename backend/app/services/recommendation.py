"""Recommendation generation service - Dedup, threshold, creation."""

import uuid
from datetime import datetime, timedelta, timezone
from decimal import Decimal

import structlog
from sqlalchemy import select, update
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.audit_log import ActorType
from app.models.deal import Deal
from app.models.email_message import EmailMessage
from app.models.email_thread import EmailThread
from app.models.intent_classification import IntentClassification
from app.models.pipeline_config import PipelineConfig
from app.models.stage_recommendation import RecommendationStatus, StageRecommendation
from app.services.audit import write_audit_log
from app.services.stage_mapper import StageMapping

logger = structlog.get_logger()


async def generate_recommendation(
    db: AsyncSession,
    *,
    email_msg: EmailMessage,
    thread: EmailThread,
    deal: Deal,
    classification: IntentClassification,
    stage_mapping: StageMapping,
    pipeline_config: PipelineConfig,
    trace_id: uuid.UUID,
) -> StageRecommendation | None:
    """Generate a stage change recommendation if all conditions are met.

    Conditions (FR-014):
        1. Email linked to deal
        2. Confidence above threshold
        3. Mapped stage differs from current stage
        4. No duplicate pending recommendation for same deal+stage
        5. Stage mapping is valid

    Also supersedes older pending recommendations for the same deal.

    Returns:
        StageRecommendation if created, None if conditions not met.
    """
    confidence = classification.confidence_score

    # Check confidence threshold
    if confidence < pipeline_config.recommendation_threshold:
        # Check if above logging threshold
        if confidence >= pipeline_config.logging_threshold:
            classification.action_taken = "below_threshold"
            await db.flush()
            await logger.ainfo(
                "below_threshold",
                confidence=float(confidence),
                threshold=float(pipeline_config.recommendation_threshold),
            )
        return None

    # Check stage mapping validity
    if not stage_mapping.is_valid:
        classification.action_taken = "no_change"
        await db.flush()
        await logger.ainfo("stage_mapping_invalid", reason=stage_mapping.reason)
        return None

    # Check for duplicate pending recommendation
    existing = await db.execute(
        select(StageRecommendation).where(
            StageRecommendation.deal_id == deal.id,
            StageRecommendation.recommended_stage == stage_mapping.target_stage_id,
            StageRecommendation.status == RecommendationStatus.PENDING,
        )
    )
    if existing.scalar_one_or_none():
        classification.action_taken = "duplicate_pending"
        await db.flush()
        await logger.ainfo("duplicate_pending_recommendation", deal_id=str(deal.id))
        return None

    # Supersede any existing pending recommendations for this deal
    await db.execute(
        update(StageRecommendation)
        .where(
            StageRecommendation.deal_id == deal.id,
            StageRecommendation.status == RecommendationStatus.PENDING,
        )
        .values(status=RecommendationStatus.SUPERSEDED)
    )

    # Calculate expiration
    timeout_hours = pipeline_config.approval_timeout_hours or 48
    expires_at = datetime.now(timezone.utc) + timedelta(hours=timeout_hours)

    # Generate idempotency key
    rec_id = uuid.uuid4()
    idempotency_key = f"rec_{rec_id}_v1"

    # Create recommendation
    recommendation = StageRecommendation(
        id=rec_id,
        email_message_id=email_msg.id,
        thread_id=thread.id,
        deal_id=deal.id,
        current_stage=deal.current_stage,
        recommended_stage=stage_mapping.target_stage_id,
        recommended_stage_name=stage_mapping.target_stage_name,
        confidence_score=classification.confidence_score,
        intent=classification.intent,
        reasoning=classification.reasoning,
        key_phrases=classification.key_phrases,
        direction=classification.direction,
        prompt_version=classification.prompt_version,
        llm_model=classification.llm_model,
        llm_latency_ms=classification.llm_latency_ms,
        status=RecommendationStatus.PENDING,
        expires_at=expires_at,
        idempotency_key=idempotency_key,
    )
    db.add(recommendation)

    # Update classification action
    classification.action_taken = "recommendation_generated"
    await db.flush()

    # Audit log
    await write_audit_log(
        db,
        action="recommendation_generated",
        entity_type="stage_recommendation",
        entity_id=recommendation.id,
        actor_type=ActorType.SYSTEM,
        trace_id=trace_id,
        after_state={
            "deal_id": str(deal.id),
            "current_stage": deal.current_stage,
            "recommended_stage": stage_mapping.target_stage_id,
            "confidence": float(confidence),
            "intent": classification.intent,
        },
    )

    await logger.ainfo(
        "recommendation_generated",
        recommendation_id=str(recommendation.id),
        deal_name=deal.deal_name,
        current_stage=deal.current_stage,
        recommended_stage=stage_mapping.target_stage_id,
        confidence=float(confidence),
    )

    return recommendation
