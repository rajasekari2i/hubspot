"""CRM updater service - Writes approved stage changes to HubSpot with conflict detection."""

import uuid
from datetime import datetime, timezone

import structlog
from sqlalchemy.ext.asyncio import AsyncSession

from app.integrations.hubspot.protocol import CRMProvider
from app.models.audit_log import ActorType
from app.models.deal import Deal
from app.models.stage_recommendation import (
    RecommendationStatus,
    StageRecommendation,
    validate_transition,
)
from app.services.audit import write_audit_log

logger = structlog.get_logger()


class CRMUpdateResult:
    """Result of a CRM update attempt."""

    def __init__(
        self,
        success: bool,
        status: RecommendationStatus,
        error: str | None = None,
    ) -> None:
        self.success = success
        self.status = status
        self.error = error


async def execute_crm_update(
    db: AsyncSession,
    hubspot_client: CRMProvider,
    recommendation: StageRecommendation,
    deal: Deal,
    actor_id: str | None = None,
    trace_id: uuid.UUID | None = None,
) -> CRMUpdateResult:
    """Execute the CRM stage update for an approved recommendation.

    Steps:
        1. Read-before-write conflict check (live stage vs expected current stage)
        2. Update deal stage in HubSpot
        3. Add audit note with transition details
        4. Update local deal cache
        5. Transition recommendation status

    Returns:
        CRMUpdateResult indicating success/failure/conflict.
    """
    # Validate the recommendation is in approved state
    if recommendation.status != RecommendationStatus.APPROVED:
        return CRMUpdateResult(
            success=False,
            status=recommendation.status,
            error=f"Recommendation not in approved state: {recommendation.status.value}",
        )

    try:
        # Step 1: Read-before-write conflict check
        stage_matches, live_stage = await hubspot_client.check_deal_stage(
            deal.hubspot_deal_id, recommendation.current_stage
        )

        if not stage_matches:
            # CRM stage was changed externally -- conflict
            recommendation.status = RecommendationStatus.CONFLICT
            recommendation.reviewed_at = datetime.now(timezone.utc)
            await db.flush()

            await write_audit_log(
                db,
                action="crm_update_conflict",
                entity_type="stage_recommendation",
                entity_id=recommendation.id,
                actor_type=ActorType.SYSTEM,
                actor_id=actor_id,
                trace_id=trace_id,
                before_state={
                    "expected_stage": recommendation.current_stage,
                    "live_stage": live_stage,
                },
                after_state={"status": RecommendationStatus.CONFLICT.value},
            )

            await logger.awarn(
                "crm_update_conflict",
                recommendation_id=str(recommendation.id),
                expected_stage=recommendation.current_stage,
                live_stage=live_stage,
            )

            return CRMUpdateResult(
                success=False,
                status=RecommendationStatus.CONFLICT,
                error=f"Stage conflict: expected '{recommendation.current_stage}', found '{live_stage}'",
            )

        # Step 2: Update deal stage in HubSpot with audit note
        note = (
            f"[Pipeline Intelligence] Stage updated: "
            f"{deal.current_stage_name} -> {recommendation.recommended_stage_name}\n"
            f"Intent: {recommendation.intent} (confidence: {float(recommendation.confidence_score):.0%})\n"
            f"Reasoning: {recommendation.reasoning}\n"
            f"Approved by: {actor_id or 'system'}\n"
            f"Recommendation ID: {recommendation.id}"
        )

        await hubspot_client.update_deal_stage(
            deal_id=deal.hubspot_deal_id,
            stage_id=recommendation.recommended_stage,
            note=note,
        )

        # Step 3: Update local deal cache
        before_stage = deal.current_stage
        before_stage_name = deal.current_stage_name
        deal.current_stage = recommendation.recommended_stage
        deal.current_stage_name = recommendation.recommended_stage_name
        deal.last_synced_at = datetime.now(timezone.utc)

        # Step 4: Transition recommendation to write_success
        recommendation.status = RecommendationStatus.WRITE_SUCCESS
        await db.flush()

        await write_audit_log(
            db,
            action="crm_update_success",
            entity_type="stage_recommendation",
            entity_id=recommendation.id,
            actor_type=ActorType.USER if actor_id else ActorType.SYSTEM,
            actor_id=actor_id,
            trace_id=trace_id,
            before_state={
                "stage": before_stage,
                "stage_name": before_stage_name,
            },
            after_state={
                "stage": recommendation.recommended_stage,
                "stage_name": recommendation.recommended_stage_name,
                "status": RecommendationStatus.WRITE_SUCCESS.value,
            },
        )

        await logger.ainfo(
            "crm_update_success",
            recommendation_id=str(recommendation.id),
            deal_id=str(deal.id),
            new_stage=recommendation.recommended_stage,
        )

        return CRMUpdateResult(
            success=True,
            status=RecommendationStatus.WRITE_SUCCESS,
        )

    except Exception as exc:
        # Step 5: Handle write failure
        if validate_transition(
            recommendation.status, RecommendationStatus.WRITE_FAILED
        ):
            recommendation.status = RecommendationStatus.WRITE_FAILED
            await db.flush()

        await write_audit_log(
            db,
            action="crm_update_failed",
            entity_type="stage_recommendation",
            entity_id=recommendation.id,
            actor_type=ActorType.SYSTEM,
            actor_id=actor_id,
            trace_id=trace_id,
            after_state={
                "status": RecommendationStatus.WRITE_FAILED.value,
                "error": str(exc),
            },
        )

        await logger.aerror(
            "crm_update_failed",
            recommendation_id=str(recommendation.id),
            error=str(exc),
        )

        return CRMUpdateResult(
            success=False,
            status=RecommendationStatus.WRITE_FAILED,
            error=str(exc),
        )
