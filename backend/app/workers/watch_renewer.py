"""Gmail watch renewal scheduled worker."""

import asyncio
from datetime import datetime, timedelta, timezone

import structlog
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import get_settings
from app.dependencies import get_session_factory
from app.models.user_config import UserConfig

logger = structlog.get_logger()


async def renew_all_watches() -> None:
    """Renew Gmail watch for all active users approaching expiration.

    Gmail watches expire after 7 days. We renew daily (well before expiry).
    """
    settings = get_settings()
    session_factory = get_session_factory()

    from app.integrations.gmail.client import GmailClient

    gmail_client = GmailClient(
        credentials={},
        project_id=settings.google_cloud_project,
    )

    async with session_factory() as db:
        # Get all active users
        result = await db.execute(
            select(UserConfig).where(UserConfig.is_active.is_(True))
        )
        users = result.scalars().all()

        success_count = 0
        failure_count = 0

        for user in users:
            try:
                watch_result = await gmail_client.renew_watch(user.email)
                user.gmail_watch_expiration = datetime.fromtimestamp(
                    int(watch_result.get("expiration", 0)) / 1000,
                    tz=timezone.utc,
                )
                success_count += 1
                await logger.ainfo(
                    "watch_renewed",
                    user_email=user.email,
                    expiration=user.gmail_watch_expiration.isoformat()
                    if user.gmail_watch_expiration
                    else None,
                )
            except Exception as exc:
                failure_count += 1
                await logger.aerror(
                    "watch_renewal_failed",
                    user_email=user.email,
                    error=str(exc),
                )

        await db.commit()

        await logger.ainfo(
            "watch_renewal_completed",
            success=success_count,
            failures=failure_count,
        )

        # Alert on failures
        if failure_count > 0:
            from app.integrations.slack.client import SlackClient

            slack_client = SlackClient(
                bot_token=settings.slack_bot_token,
                signing_secret=settings.slack_signing_secret,
            )
            await slack_client.send_alert(
                channel=settings.slack_alert_channel,
                text=f"Gmail watch renewal: {failure_count} failures out of {success_count + failure_count} users",
            )


async def check_inactivity() -> None:
    """Detect users with no email activity in 24 hours (silent watch expiration)."""
    session_factory = get_session_factory()

    async with session_factory() as db:
        threshold = datetime.now(timezone.utc) - timedelta(hours=24)
        result = await db.execute(
            select(UserConfig).where(
                UserConfig.is_active.is_(True),
                UserConfig.gmail_watch_expiration < threshold,
            )
        )
        inactive_users = result.scalars().all()

        if inactive_users:
            settings = get_settings()
            from app.integrations.slack.client import SlackClient

            slack_client = SlackClient(
                bot_token=settings.slack_bot_token,
                signing_secret=settings.slack_signing_secret,
            )
            user_list = ", ".join(u.email for u in inactive_users)
            await slack_client.send_alert(
                channel=settings.slack_alert_channel,
                text=f"No email activity in 24h for: {user_list}. Gmail watches may have expired.",
            )


if __name__ == "__main__":
    asyncio.run(renew_all_watches())
