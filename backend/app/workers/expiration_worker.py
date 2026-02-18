"""Recommendation expiration worker - Expires stale pending/snoozed recommendations."""

import asyncio
from datetime import datetime, timezone

import structlog
from sqlalchemy import select

from app.config import get_settings
from app.dependencies import get_session_factory
from app.integrations.slack.client import SlackClient
from app.models.audit_log import ActorType
from app.models.deal import Deal
from app.models.stage_recommendation import (
    RecommendationStatus,
    StageRecommendation,
    validate_transition,
)
from app.services.audit import write_audit_log
from app.services.notification import update_recommendation_message

logger = structlog.get_logger()


async def expire_stale_recommendations() -> None:
    """Find and expire all recommendations past their expiration time.

    Processes recommendations in pending or snoozed status where
    expires_at < now(). For each:
        1. Transition status to expired
        2. Update the Slack message
        3. Write an audit log entry
    """
    settings = get_settings()
    session_factory = get_session_factory()
    now = datetime.now(timezone.utc)

    slack_client = SlackClient(
        bot_token=settings.slack_bot_token,
        signing_secret=settings.slack_signing_secret,
    )

    async with session_factory() as db:
        # Query all expired pending/snoozed recommendations
        result = await db.execute(
            select(StageRecommendation).where(
                StageRecommendation.status.in_([
                    RecommendationStatus.PENDING,
                    RecommendationStatus.SNOOZED,
                ]),
                StageRecommendation.expires_at < now,
            )
        )
        expired_recs = result.scalars().all()

        if not expired_recs:
            await logger.ainfo("expiration_check_complete", expired_count=0)
            return

        success_count = 0
        failure_count = 0

        for rec in expired_recs:
            try:
                if not validate_transition(rec.status, RecommendationStatus.EXPIRED):
                    continue

                before_status = rec.status.value
                rec.status = RecommendationStatus.EXPIRED
                rec.reviewed_at = now
                await db.flush()

                # Get deal for Slack message update
                deal_result = await db.execute(
                    select(Deal).where(Deal.id == rec.deal_id)
                )
                deal = deal_result.scalar_one_or_none()

                if deal:
                    await update_recommendation_message(
                        slack_client, rec, deal,
                        action_text="Expired (no action taken)",
                    )

                await write_audit_log(
                    db,
                    action="recommendation_expired",
                    entity_type="stage_recommendation",
                    entity_id=rec.id,
                    actor_type=ActorType.SYSTEM,
                    before_state={"status": before_status},
                    after_state={"status": "expired"},
                )

                success_count += 1

            except Exception as exc:
                failure_count += 1
                await logger.aerror(
                    "expiration_failed",
                    recommendation_id=str(rec.id),
                    error=str(exc),
                )

        await db.commit()

        await logger.ainfo(
            "expiration_check_complete",
            expired_count=success_count,
            failures=failure_count,
        )

        # Alert on failures
        if failure_count > 0:
            await slack_client.send_alert(
                channel=settings.slack_alert_channel,
                text=f"Recommendation expiration: {failure_count} failures out of {success_count + failure_count}",
            )


if __name__ == "__main__":
    asyncio.run(expire_stale_recommendations())
