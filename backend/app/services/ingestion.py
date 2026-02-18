"""Email ingestion service - Fetch, parse, and persist email metadata."""

import uuid
from datetime import datetime, timezone

import structlog
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.integrations.gmail.protocol import EmailProvider
from app.models.audit_log import ActorType
from app.models.email_message import EmailMessage, ProcessingStatus
from app.services.audit import write_audit_log

logger = structlog.get_logger()


async def ingest_new_emails(
    db: AsyncSession,
    gmail_client: EmailProvider,
    user_email: str,
    user_id: uuid.UUID,
    start_history_id: int,
    trace_id: uuid.UUID,
) -> list[EmailMessage]:
    """Fetch new emails since the last history ID and persist metadata.

    Args:
        db: Database session.
        gmail_client: Gmail API client.
        user_email: User's email address.
        user_id: Internal user ID.
        start_history_id: Last processed Gmail history ID.
        trace_id: End-to-end trace ID.

    Returns:
        List of newly persisted EmailMessage records.
    """
    await logger.ainfo(
        "ingestion_started",
        user_email=user_email,
        start_history_id=start_history_id,
    )

    # Fetch history changes from Gmail
    history_records = await gmail_client.get_history(user_email, start_history_id)

    if not history_records:
        await logger.ainfo("no_new_messages", user_email=user_email)
        return []

    new_messages: list[EmailMessage] = []

    for record in history_records:
        message_id = record.get("message_id")
        if not message_id:
            continue

        # Check for duplicate
        existing = await db.execute(
            select(EmailMessage).where(EmailMessage.gmail_message_id == message_id)
        )
        if existing.scalar_one_or_none():
            continue

        # Fetch full message metadata
        msg_data = await gmail_client.get_message(user_email, message_id)

        email_msg = EmailMessage(
            gmail_message_id=message_id,
            gmail_thread_id=msg_data.get("gmail_thread_id", ""),
            gmail_history_id=record.get("history_id", start_history_id),
            user_id=user_id,
            from_address=msg_data.get("from_address", ""),
            to_addresses=msg_data.get("to_addresses", []),
            cc_addresses=msg_data.get("cc_addresses", []),
            subject=msg_data.get("subject", ""),
            body_excerpt=msg_data.get("snippet", "")[:500] if msg_data.get("snippet") else None,
            received_at=msg_data.get("date", datetime.now(timezone.utc)),
            processing_status=ProcessingStatus.PENDING,
            trace_id=trace_id,
        )
        db.add(email_msg)
        new_messages.append(email_msg)

    await db.flush()

    # Audit log for each ingested message
    for msg in new_messages:
        await write_audit_log(
            db,
            action="email_processed",
            entity_type="email_message",
            entity_id=msg.id,
            actor_type=ActorType.SYSTEM,
            trace_id=trace_id,
            after_state={"gmail_message_id": msg.gmail_message_id, "subject": msg.subject},
        )

    await logger.ainfo(
        "ingestion_completed",
        user_email=user_email,
        new_messages=len(new_messages),
    )

    return new_messages
