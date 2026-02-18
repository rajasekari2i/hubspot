"""Audit routes - Query audit trail for entities."""

import uuid

import structlog
from fastapi import APIRouter, Depends, Query
from pydantic import BaseModel
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.middleware.auth import require_roles
from app.dependencies import get_db
from app.models.audit_log import AuditLog
from app.models.user_config import UserConfig, UserRole

logger = structlog.get_logger()

router = APIRouter(prefix="/audit", tags=["Audit"])


# ---------- Response schemas ----------


class AuditLogEntry(BaseModel):
    id: str
    trace_id: str | None = None
    action: str
    entity_type: str
    entity_id: str
    actor_type: str
    actor_id: str | None = None
    before_state: dict | None = None
    after_state: dict | None = None
    metadata: dict | None = None
    created_at: str

    class Config:
        from_attributes = True


class PaginatedAuditTrail(BaseModel):
    items: list[AuditLogEntry]
    total: int
    page: int
    page_size: int
    total_pages: int


# ---------- Routes ----------


@router.get("/trail/{entity_type}/{entity_id}", response_model=PaginatedAuditTrail)
async def get_audit_trail(
    entity_type: str,
    entity_id: uuid.UUID,
    page: int = Query(1, ge=1, description="Page number"),
    page_size: int = Query(20, ge=1, le=100, description="Items per page"),
    db: AsyncSession = Depends(get_db),
    current_user: UserConfig = Depends(require_roles(UserRole.ADMIN, UserRole.REVOPS)),
) -> PaginatedAuditTrail:
    """Get paginated audit trail for a specific entity.

    Returns all audit log entries matching the given entity_type and entity_id,
    ordered by created_at descending (most recent first).
    Requires revops or admin role.
    """
    base_filter = [
        AuditLog.entity_type == entity_type,
        AuditLog.entity_id == entity_id,
    ]

    # Count total
    count_query = select(func.count(AuditLog.id)).where(*base_filter)
    total_result = await db.execute(count_query)
    total = total_result.scalar_one()

    # Fetch paginated results
    offset = (page - 1) * page_size
    query = (
        select(AuditLog)
        .where(*base_filter)
        .order_by(AuditLog.created_at.desc())
        .offset(offset)
        .limit(page_size)
    )

    result = await db.execute(query)
    entries = result.scalars().all()

    items = [
        AuditLogEntry(
            id=str(entry.id),
            trace_id=str(entry.trace_id) if entry.trace_id else None,
            action=entry.action,
            entity_type=entry.entity_type,
            entity_id=str(entry.entity_id),
            actor_type=entry.actor_type.value,
            actor_id=entry.actor_id,
            before_state=entry.before_state,
            after_state=entry.after_state,
            metadata=entry.metadata_,
            created_at=entry.created_at.isoformat(),
        )
        for entry in entries
    ]

    total_pages = (total + page_size - 1) // page_size if total > 0 else 0

    await logger.ainfo(
        "audit_trail_retrieved",
        entity_type=entity_type,
        entity_id=str(entity_id),
        total=total,
        page=page,
        actor=current_user.email,
    )

    return PaginatedAuditTrail(
        items=items,
        total=total,
        page=page,
        page_size=page_size,
        total_pages=total_pages,
    )
