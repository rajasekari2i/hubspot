"""EmailMessage ORM model - Gmail message metadata."""

import enum
import uuid
from datetime import datetime

from sqlalchemy import BigInteger, DateTime, Enum, Index, String, func
from sqlalchemy.dialects.postgresql import ARRAY, UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base, UUIDPrimaryKeyMixin


class ProcessingStatus(str, enum.Enum):
    PENDING = "pending"
    PROCESSING = "processing"
    CLASSIFIED = "classified"
    FAILED = "failed"


class EmailMessage(Base, UUIDPrimaryKeyMixin):
    __tablename__ = "email_messages"

    gmail_message_id: Mapped[str] = mapped_column(String(50), unique=True, nullable=False)
    gmail_thread_id: Mapped[str] = mapped_column(String(50), nullable=False)
    gmail_history_id: Mapped[int] = mapped_column(BigInteger, nullable=False)
    user_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), nullable=False, index=True
    )
    from_address: Mapped[str] = mapped_column(String(255), nullable=False)
    to_addresses: Mapped[list[str]] = mapped_column(ARRAY(String), nullable=False)
    cc_addresses: Mapped[list[str]] = mapped_column(ARRAY(String), server_default="{}")
    subject: Mapped[str] = mapped_column(String(500), nullable=False)
    body_excerpt: Mapped[str | None] = mapped_column(String(500), nullable=True)
    received_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    processed_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    processing_status: Mapped[ProcessingStatus] = mapped_column(
        Enum(ProcessingStatus), server_default="pending", nullable=False
    )
    trace_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )

    __table_args__ = (
        Index("ix_email_messages_gmail_thread_id", "gmail_thread_id"),
        Index("ix_email_messages_user_received", "user_id", "received_at"),
        Index("ix_email_messages_processing_status", "processing_status"),
        Index("ix_email_messages_trace_id", "trace_id"),
    )
