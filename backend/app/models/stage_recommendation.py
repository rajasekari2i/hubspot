"""StageRecommendation ORM model - Core workflow entity with state machine."""

import enum
import uuid
from datetime import datetime
from decimal import Decimal

from sqlalchemy import (
    CheckConstraint,
    DateTime,
    Enum,
    ForeignKey,
    Index,
    Integer,
    Numeric,
    String,
    Text,
    UniqueConstraint,
    func,
)
from sqlalchemy.dialects.postgresql import ARRAY, UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base, TimestampMixin, UUIDPrimaryKeyMixin
from app.models.intent_classification import Direction


class RecommendationStatus(str, enum.Enum):
    PENDING = "pending"
    APPROVED = "approved"
    REJECTED = "rejected"
    EXPIRED = "expired"
    SUPERSEDED = "superseded"
    SNOOZED = "snoozed"
    WRITE_SUCCESS = "write_success"
    WRITE_FAILED = "write_failed"
    CONFLICT = "conflict"


# Valid state transitions
VALID_TRANSITIONS: dict[RecommendationStatus, set[RecommendationStatus]] = {
    RecommendationStatus.PENDING: {
        RecommendationStatus.APPROVED,
        RecommendationStatus.REJECTED,
        RecommendationStatus.EXPIRED,
        RecommendationStatus.SUPERSEDED,
        RecommendationStatus.SNOOZED,
    },
    RecommendationStatus.SNOOZED: {
        RecommendationStatus.PENDING,
        RecommendationStatus.EXPIRED,
    },
    RecommendationStatus.APPROVED: {
        RecommendationStatus.WRITE_SUCCESS,
        RecommendationStatus.WRITE_FAILED,
        RecommendationStatus.CONFLICT,
    },
}


def validate_transition(
    current: RecommendationStatus, target: RecommendationStatus
) -> bool:
    """Check if a state transition is valid per the state machine."""
    allowed = VALID_TRANSITIONS.get(current, set())
    return target in allowed


class StageRecommendation(Base, UUIDPrimaryKeyMixin, TimestampMixin):
    __tablename__ = "stage_recommendations"

    email_message_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("email_messages.id"), nullable=False
    )
    thread_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("email_threads.id"), nullable=False
    )
    deal_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("deals.id"), nullable=False
    )
    current_stage: Mapped[str] = mapped_column(String(50), nullable=False)
    recommended_stage: Mapped[str] = mapped_column(String(50), nullable=False)
    recommended_stage_name: Mapped[str] = mapped_column(String(255), nullable=False)
    confidence_score: Mapped[Decimal] = mapped_column(Numeric(4, 3), nullable=False)
    intent: Mapped[str] = mapped_column(String(50), nullable=False)
    reasoning: Mapped[str] = mapped_column(Text, nullable=False)
    key_phrases: Mapped[list[str]] = mapped_column(ARRAY(String), server_default="{}")
    direction: Mapped[Direction] = mapped_column(Enum(Direction), nullable=False)
    prompt_version: Mapped[str] = mapped_column(String(20), nullable=False)
    llm_model: Mapped[str] = mapped_column(String(50), nullable=False)
    llm_latency_ms: Mapped[int | None] = mapped_column(Integer, nullable=True)
    status: Mapped[RecommendationStatus] = mapped_column(
        Enum(RecommendationStatus), server_default="pending", nullable=False
    )
    reviewed_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    reviewed_by: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("user_configs.id"), nullable=True
    )
    rejection_reason: Mapped[str | None] = mapped_column(String(50), nullable=True)
    user_corrected_stage: Mapped[str | None] = mapped_column(String(50), nullable=True)
    slack_message_ts: Mapped[str | None] = mapped_column(String(50), nullable=True)
    slack_channel_id: Mapped[str | None] = mapped_column(String(50), nullable=True)
    snooze_count: Mapped[int] = mapped_column(Integer, server_default="0")
    expires_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    idempotency_key: Mapped[str] = mapped_column(String(100), unique=True, nullable=False)

    __table_args__ = (
        CheckConstraint(
            "confidence_score >= 0.000 AND confidence_score <= 1.000",
            name="ck_stage_recommendations_confidence",
        ),
        Index("ix_stage_recommendations_deal_status", "deal_id", "status"),
        Index("ix_stage_recommendations_status_expires", "status", "expires_at"),
        Index("ix_stage_recommendations_reviewed_by", "reviewed_by"),
        Index("ix_stage_recommendations_created_at", "created_at"),
    )
