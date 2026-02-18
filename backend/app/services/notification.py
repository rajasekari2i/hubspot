"""Notification service - Slack recommendation delivery and message updates."""

import structlog
from sqlalchemy.ext.asyncio import AsyncSession

from app.integrations.slack.protocol import MessagingProvider
from app.models.deal import Deal
from app.models.stage_recommendation import RecommendationStatus, StageRecommendation
from app.models.user_config import UserConfig

logger = structlog.get_logger()


async def send_recommendation_notification(
    db: AsyncSession,
    slack_client: MessagingProvider,
    recommendation: StageRecommendation,
    deal: Deal,
    user: UserConfig,
) -> bool:
    """Send a recommendation notification to the deal owner via Slack.

    Builds a Block Kit message with deal info, confidence badge, and action buttons.
    Stores the Slack message timestamp for later updates.

    Returns:
        True if notification was sent successfully.
    """
    if not user.slack_user_id:
        await logger.awarn(
            "no_slack_user_id",
            user_email=user.email,
            recommendation_id=str(recommendation.id),
        )
        return False

    # Build recommendation data for the Slack client
    confidence_float = float(recommendation.confidence_score)
    recommendation_data = {
        "recommendation_id": str(recommendation.id),
        "deal_name": deal.deal_name,
        "deal_id": str(deal.id),
        "hubspot_deal_id": deal.hubspot_deal_id,
        "current_stage": deal.current_stage_name,
        "recommended_stage": recommendation.recommended_stage_name,
        "confidence_score": confidence_float,
        "intent": recommendation.intent,
        "reasoning": recommendation.reasoning,
        "key_phrases": recommendation.key_phrases,
        "direction": recommendation.direction.value if hasattr(recommendation.direction, 'value') else str(recommendation.direction),
        "expires_at": recommendation.expires_at.isoformat(),
    }

    try:
        result = await slack_client.send_recommendation(
            channel_or_user=user.slack_user_id,
            recommendation_data=recommendation_data,
        )

        # Store Slack message metadata for later updates
        recommendation.slack_message_ts = result.get("ts")
        recommendation.slack_channel_id = result.get("channel")
        await db.flush()

        await logger.ainfo(
            "notification_sent",
            recommendation_id=str(recommendation.id),
            slack_user=user.slack_user_id,
        )
        return True

    except Exception as exc:
        await logger.aerror(
            "notification_failed",
            recommendation_id=str(recommendation.id),
            error=str(exc),
        )
        return False


async def update_recommendation_message(
    slack_client: MessagingProvider,
    recommendation: StageRecommendation,
    deal: Deal,
    action_text: str,
    actor_name: str = "",
) -> bool:
    """Update an existing Slack message after an action (approve/reject/expire).

    Replaces action buttons with a status message.
    """
    if not recommendation.slack_channel_id or not recommendation.slack_message_ts:
        return False

    status_emoji = {
        RecommendationStatus.APPROVED: "white_check_mark",
        RecommendationStatus.WRITE_SUCCESS: "white_check_mark",
        RecommendationStatus.REJECTED: "x",
        RecommendationStatus.EXPIRED: "hourglass",
        RecommendationStatus.SUPERSEDED: "arrows_counterclockwise",
        RecommendationStatus.CONFLICT: "warning",
        RecommendationStatus.WRITE_FAILED: "exclamation",
        RecommendationStatus.SNOOZED: "zzz",
    }
    emoji = status_emoji.get(recommendation.status, "information_source")

    # Build detail text based on status
    detail_lines = [
        f"*{deal.deal_name}*",
        f"{deal.current_stage_name} → {recommendation.recommended_stage_name}",
        f":{emoji}: *{action_text}*" + (f" by {actor_name}" if actor_name else ""),
    ]

    if recommendation.status == RecommendationStatus.REJECTED and recommendation.rejection_reason:
        detail_lines.append(f"Reason: _{recommendation.rejection_reason}_")
        if recommendation.user_corrected_stage:
            detail_lines.append(f"Corrected stage: {recommendation.user_corrected_stage}")

    if recommendation.status == RecommendationStatus.CONFLICT:
        detail_lines.append("The deal stage was changed externally before this update could be applied.")

    if recommendation.status == RecommendationStatus.SNOOZED:
        detail_lines.append(f"Snooze count: {recommendation.snooze_count}")

    updated_blocks = [
        {
            "type": "section",
            "text": {
                "type": "mrkdwn",
                "text": "\n".join(detail_lines),
            },
        }
    ]

    try:
        await slack_client.update_message(
            channel=recommendation.slack_channel_id,
            message_ts=recommendation.slack_message_ts,
            updated_blocks=updated_blocks,
        )
        return True
    except Exception as exc:
        await logger.aerror("message_update_failed", error=str(exc))
        return False
