"""Audit log service - Write immutable audit trail entries."""

import uuid
from typing import Any

import structlog
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.audit_log import ActorType, AuditLog

logger = structlog.get_logger()


async def write_audit_log(
    db: AsyncSession,
    *,
    action: str,
    entity_type: str,
    entity_id: uuid.UUID,
    actor_type: ActorType = ActorType.SYSTEM,
    actor_id: str | None = None,
    trace_id: uuid.UUID | None = None,
    before_state: dict[str, Any] | None = None,
    after_state: dict[str, Any] | None = None,
    metadata: dict[str, Any] | None = None,
) -> AuditLog:
    """Create an immutable audit log entry.

    Args:
        db: Database session.
        action: Action performed (e.g., 'recommendation_approved').
        entity_type: Type of entity affected (e.g., 'stage_recommendation').
        entity_id: ID of the entity affected.
        actor_type: Whether the actor is a system or user.
        actor_id: User ID or service name.
        trace_id: End-to-end trace correlation ID.
        before_state: State before the action.
        after_state: State after the action.
        metadata: Additional context.
    """
    entry = AuditLog(
        trace_id=trace_id,
        action=action,
        entity_type=entity_type,
        entity_id=entity_id,
        actor_type=actor_type,
        actor_id=actor_id,
        before_state=before_state,
        after_state=after_state,
        metadata_=metadata or {},
    )
    db.add(entry)
    await db.flush()

    await logger.ainfo(
        "audit_log_written",
        action=action,
        entity_type=entity_type,
        entity_id=str(entity_id),
        actor_id=actor_id,
    )

    return entry
