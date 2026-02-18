"""OAuth token proactive refresh worker.

Queries credentials approaching expiry, refreshes tokens via the appropriate
provider, re-encrypts, and alerts on persistent failures.
"""

import asyncio
from datetime import datetime, timedelta, timezone

import structlog
from sqlalchemy import select

from app.config import get_settings
from app.dependencies import get_session_factory
from app.models.audit_log import ActorType
from app.models.credential import Credential, ProviderType
from app.models.user_config import UserConfig
from app.services.audit import write_audit_log
from app.utils.encryption import decrypt, encrypt

logger = structlog.get_logger()

# Refresh tokens that expire within this window
_REFRESH_WINDOW = timedelta(minutes=15)


async def _refresh_google_token(refresh_token: str, settings) -> dict:
    """Exchange a Google OAuth2 refresh token for a new access token."""
    import aiohttp

    async with aiohttp.ClientSession() as session:
        async with session.post(
            "https://oauth2.googleapis.com/token",
            data={
                "client_id": settings.google_client_id,
                "client_secret": settings.google_client_secret,
                "refresh_token": refresh_token,
                "grant_type": "refresh_token",
            },
        ) as resp:
            resp.raise_for_status()
            return await resp.json()


async def refresh_expiring_tokens() -> None:
    """Find credentials nearing expiry and refresh them proactively."""
    settings = get_settings()
    session_factory = get_session_factory()
    threshold = datetime.now(timezone.utc) + _REFRESH_WINDOW

    async with session_factory() as db:
        result = await db.execute(
            select(Credential)
            .join(UserConfig, Credential.user_id == UserConfig.id)
            .where(
                UserConfig.is_active.is_(True),
                Credential.token_expiry < threshold,
                Credential.refresh_token_enc.isnot(None),
            )
        )
        credentials = result.scalars().all()

        if not credentials:
            await logger.ainfo("token_refresh.check_complete", refreshed=0)
            return

        success_count = 0
        failure_count = 0

        for cred in credentials:
            try:
                refresh_token = decrypt(cred.refresh_token_enc, settings.encryption_key)

                if cred.provider == ProviderType.GMAIL:
                    token_data = await _refresh_google_token(refresh_token, settings)
                else:
                    await logger.awarning(
                        "token_refresh.unsupported_provider",
                        provider=cred.provider.value,
                        credential_id=str(cred.id),
                    )
                    continue

                new_access_token = token_data["access_token"]
                expires_in = token_data.get("expires_in", 3600)
                new_expiry = datetime.now(timezone.utc) + timedelta(seconds=expires_in)

                cred.access_token_enc = encrypt(new_access_token, settings.encryption_key)
                cred.token_expiry = new_expiry

                # If a new refresh token was issued, update it
                if "refresh_token" in token_data:
                    cred.refresh_token_enc = encrypt(
                        token_data["refresh_token"], settings.encryption_key
                    )

                await db.flush()

                await write_audit_log(
                    db,
                    action="token_refreshed",
                    entity_type="credential",
                    entity_id=cred.id,
                    actor_type=ActorType.SYSTEM,
                    actor_id="token_refresher",
                    before_state={"token_expiry": threshold.isoformat()},
                    after_state={"token_expiry": new_expiry.isoformat()},
                )

                success_count += 1
                await logger.ainfo(
                    "token_refresh.success",
                    credential_id=str(cred.id),
                    provider=cred.provider.value,
                    new_expiry=new_expiry.isoformat(),
                )

            except Exception as exc:
                failure_count += 1
                await logger.aerror(
                    "token_refresh.failed",
                    credential_id=str(cred.id),
                    provider=cred.provider.value,
                    error=str(exc),
                )

        await db.commit()

        await logger.ainfo(
            "token_refresh.check_complete",
            refreshed=success_count,
            failures=failure_count,
        )

        # Alert on failures
        if failure_count > 0:
            try:
                from app.integrations.slack.client import SlackClient

                slack = SlackClient(
                    bot_token=settings.slack_bot_token,
                    signing_secret=settings.slack_signing_secret,
                )
                await slack.send_alert(
                    channel=settings.slack_alert_channel,
                    text=f"Token refresh: {failure_count} failures out of {success_count + failure_count} credentials",
                )
            except Exception:
                pass


if __name__ == "__main__":
    asyncio.run(refresh_expiring_tokens())
