"""EmailThread ORM model - Gmail thread to HubSpot deal mapping."""

import uuid
from datetime import datetime
from decimal import Decimal

from sqlalchemy import DateTime, ForeignKey, Index, Integer, Numeric, String, func
from sqlalchemy.dialects.postgresql import ARRAY, UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base, TimestampMixin, UUIDPrimaryKeyMixin


class EmailThread(Base, UUIDPrimaryKeyMixin, TimestampMixin):
    __tablename__ = "email_threads"

    gmail_thread_id: Mapped[str] = mapped_column(String(50), unique=True, nullable=False)
    deal_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("deals.id"), nullable=True
    )
    contact_ids: Mapped[list[uuid.UUID]] = mapped_column(
        ARRAY(UUID(as_uuid=True)), server_default="{}"
    )
    subject: Mapped[str | None] = mapped_column(String(500), nullable=True)
    message_count: Mapped[int] = mapped_column(Integer, server_default="0")
    last_activity_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    link_confidence: Mapped[Decimal | None] = mapped_column(
        Numeric(4, 3), nullable=True
    )
    link_method: Mapped[str | None] = mapped_column(String(50), nullable=True)

    __table_args__ = (Index("ix_email_threads_deal_id", "deal_id"),)
