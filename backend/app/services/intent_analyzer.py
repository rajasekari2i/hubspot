"""Intent analyzer service - LLM classification orchestration."""

import uuid
from datetime import datetime, timezone
from decimal import Decimal

import structlog
from sqlalchemy.ext.asyncio import AsyncSession

from app.integrations.llm.base import ClassificationResult, LLMProvider
from app.models.audit_log import ActorType
from app.models.email_message import EmailMessage, ProcessingStatus
from app.models.intent_classification import Direction, IntentClassification
from app.models.prompt_version import PromptVersion
from app.services.audit import write_audit_log
from app.services.pii_redactor import redact_pii

logger = structlog.get_logger()


async def classify_email_intent(
    db: AsyncSession,
    llm_provider: LLMProvider,
    email_msg: EmailMessage,
    deal_context: dict,
    active_prompt: PromptVersion,
    trace_id: uuid.UUID,
) -> IntentClassification:
    """Classify an email's deal progression intent using LLM.

    Steps:
        1. Build classification context (deal stage, thread history)
        2. Redact PII from email content
        3. Call LLM provider for classification
        4. Persist IntentClassification record
        5. Update email processing status

    Args:
        db: Database session.
        llm_provider: LLM client (primary or fallback).
        email_msg: The email to classify.
        deal_context: Dict with deal_name, current_stage, current_stage_name, thread_summary.
        active_prompt: The active PromptVersion to use.
        trace_id: End-to-end trace ID.

    Returns:
        The persisted IntentClassification record.
    """
    # Update email status to processing
    email_msg.processing_status = ProcessingStatus.PROCESSING
    await db.flush()

    # PII redaction
    safe_content = redact_pii(email_msg.body_excerpt or "")
    safe_subject = redact_pii(email_msg.subject)

    # Build context for the LLM
    context = {
        "deal_name": deal_context.get("deal_name", "Unknown"),
        "current_stage": deal_context.get("current_stage_name", "Unknown"),
        "email_subject": safe_subject,
        "thread_summary": deal_context.get("thread_summary", ""),
    }

    # Extract intent categories
    categories = active_prompt.intent_categories
    if isinstance(categories, dict):
        category_list = list(categories.keys()) if categories else []
    elif isinstance(categories, list):
        category_list = categories
    else:
        category_list = []

    # Call LLM
    try:
        result: ClassificationResult = await llm_provider.classify_intent(
            email_content=f"Subject: {safe_subject}\n\n{safe_content}",
            context=context,
            system_prompt=active_prompt.system_prompt,
            prompt_template=active_prompt.prompt_template,
            intent_categories=category_list,
        )
    except Exception as exc:
        await logger.aerror("classification_failed", error=str(exc))
        email_msg.processing_status = ProcessingStatus.FAILED
        await db.flush()
        raise

    # Map direction string to enum
    direction_map = {
        "forward": Direction.FORWARD,
        "backward": Direction.BACKWARD,
        "neutral": Direction.NEUTRAL,
    }
    direction = direction_map.get(result.direction, Direction.NEUTRAL)

    # Determine action taken
    confidence = Decimal(str(result.confidence_score))
    action_taken = "recommendation_generated"  # Default; overridden by recommendation service

    # Persist classification
    classification = IntentClassification(
        email_message_id=email_msg.id,
        deal_id=deal_context.get("deal_id"),
        intent=result.intent,
        confidence_score=confidence,
        reasoning=result.reasoning,
        key_phrases=result.key_phrases,
        direction=direction,
        prompt_version=active_prompt.version,
        llm_model=result.model,
        llm_latency_ms=result.latency_ms,
        input_tokens=result.input_tokens,
        output_tokens=result.output_tokens,
        action_taken=action_taken,
    )
    db.add(classification)

    # Update email status
    email_msg.processing_status = ProcessingStatus.CLASSIFIED
    email_msg.processed_at = datetime.now(timezone.utc)
    await db.flush()

    # Audit log
    await write_audit_log(
        db,
        action="intent_classified",
        entity_type="intent_classification",
        entity_id=classification.id,
        actor_type=ActorType.SYSTEM,
        trace_id=trace_id,
        after_state={
            "intent": result.intent,
            "confidence": float(confidence),
            "direction": result.direction,
            "model": result.model,
        },
    )

    await logger.ainfo(
        "classification_completed",
        intent=result.intent,
        confidence=float(confidence),
        direction=result.direction,
        latency_ms=result.latency_ms,
    )

    return classification
