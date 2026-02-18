"""Dead Letter Queue processor worker.

Retries failed messages from the Redis DLQ with exponential backoff.
After exceeding the max retry count, messages overflow to the
``dead_messages`` PostgreSQL table for manual resolution.
"""

import asyncio
import json
from datetime import datetime, timezone

import structlog

from app.config import get_settings
from app.dependencies import get_redis, get_session_factory
from app.models.dead_message import DeadMessage

logger = structlog.get_logger()

# Redis DLQ key prefix
DLQ_KEY = "dlq:messages"
DLQ_PROCESSING_KEY = "dlq:processing"
MAX_RETRIES = 10
BATCH_SIZE = 50


async def _reprocess_message(payload: dict) -> None:
    """Attempt to reprocess a DLQ message through its original handler.

    Dispatches based on the ``component`` field in the payload.
    """
    component = payload.get("component", "unknown")

    if component == "pubsub_consumer":
        from app.workers.pubsub_consumer import process_notification

        await process_notification(payload.get("data", {}))
    else:
        raise ValueError(f"Unknown DLQ component: {component}")


async def _overflow_to_db(
    payload: dict, error_message: str, retry_count: int
) -> None:
    """Persist a permanently-failed message to the dead_messages table."""
    session_factory = get_session_factory()
    now = datetime.now(timezone.utc)

    async with session_factory() as db:
        dead_msg = DeadMessage(
            component=payload.get("component", "unknown"),
            original_payload=payload.get("data", payload),
            error_message=error_message,
            retry_count=retry_count,
            trace_id=payload.get("trace_id"),
            first_failed_at=datetime.fromisoformat(
                payload.get("first_failed_at", now.isoformat())
            ),
            last_failed_at=now,
        )
        db.add(dead_msg)
        await db.commit()

    await logger.ainfo(
        "dlq.overflow_to_db",
        component=payload.get("component"),
        retry_count=retry_count,
    )


async def process_dlq() -> None:
    """Process messages from the Redis DLQ.

    For each message:
    1. Attempt reprocessing
    2. On success, remove from DLQ
    3. On failure, increment retry count and either re-queue or overflow to DB
    """
    settings = get_settings()
    redis = await get_redis()

    processed = 0
    succeeded = 0
    overflowed = 0
    requeued = 0

    for _ in range(BATCH_SIZE):
        # Pop a message from the DLQ
        raw = await redis.lpop(DLQ_KEY)
        if raw is None:
            break

        processed += 1

        try:
            payload = json.loads(raw)
        except json.JSONDecodeError as exc:
            await logger.aerror("dlq.invalid_json", error=str(exc))
            continue

        retry_count = payload.get("retry_count", 0) + 1
        payload["retry_count"] = retry_count

        if retry_count > MAX_RETRIES:
            # Overflow to PostgreSQL
            error_msg = payload.get("last_error", "Max retries exceeded")
            await _overflow_to_db(payload, error_msg, retry_count)
            overflowed += 1
            continue

        try:
            await _reprocess_message(payload)
            succeeded += 1
            await logger.ainfo(
                "dlq.reprocess_success",
                component=payload.get("component"),
                retry_count=retry_count,
            )
        except Exception as exc:
            payload["last_error"] = str(exc)
            if "first_failed_at" not in payload:
                payload["first_failed_at"] = datetime.now(timezone.utc).isoformat()

            # Re-queue at the end of the DLQ
            await redis.rpush(DLQ_KEY, json.dumps(payload))
            requeued += 1
            await logger.awarning(
                "dlq.reprocess_failed",
                component=payload.get("component"),
                retry_count=retry_count,
                error=str(exc),
            )

    await logger.ainfo(
        "dlq.batch_complete",
        processed=processed,
        succeeded=succeeded,
        requeued=requeued,
        overflowed=overflowed,
    )

    # Alert if messages are overflowing
    if overflowed > 0:
        try:
            from app.integrations.slack.client import SlackClient

            slack = SlackClient(
                bot_token=settings.slack_bot_token,
                signing_secret=settings.slack_signing_secret,
            )
            await slack.send_alert(
                channel=settings.slack_alert_channel,
                text=f"DLQ: {overflowed} messages exceeded max retries and moved to dead_messages table",
            )
        except Exception:
            pass

    # Report DLQ depth
    depth = await redis.llen(DLQ_KEY)
    if depth > 0:
        await logger.ainfo("dlq.depth", remaining=depth)


if __name__ == "__main__":
    asyncio.run(process_dlq())
