"""IntentClassification ORM model - LLM classification results."""

import enum
import uuid
from datetime import datetime
from decimal import Decimal

from sqlalchemy import CheckConstraint, DateTime, Enum, ForeignKey, Index, Integer, Numeric, String, Text, func
from sqlalchemy.dialects.postgresql import ARRAY, UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base, UUIDPrimaryKeyMixin


class Direction(str, enum.Enum):
    FORWARD = "forward"
    BACKWARD = "backward"
    NEUTRAL = "neutral"


class IntentClassification(Base, UUIDPrimaryKeyMixin):
    __tablename__ = "intent_classifications"

    email_message_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("email_messages.id"), nullable=False
    )
    deal_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("deals.id"), nullable=True
    )
    intent: Mapped[str] = mapped_column(String(50), nullable=False)
    confidence_score: Mapped[Decimal] = mapped_column(Numeric(4, 3), nullable=False)
    reasoning: Mapped[str] = mapped_column(Text, nullable=False)
    key_phrases: Mapped[list[str]] = mapped_column(ARRAY(String), server_default="{}")
    direction: Mapped[Direction] = mapped_column(Enum(Direction), nullable=False)
    prompt_version: Mapped[str] = mapped_column(String(20), nullable=False)
    llm_model: Mapped[str] = mapped_column(String(50), nullable=False)
    llm_latency_ms: Mapped[int] = mapped_column(Integer, nullable=False)
    input_tokens: Mapped[int | None] = mapped_column(Integer, nullable=True)
    output_tokens: Mapped[int | None] = mapped_column(Integer, nullable=True)
    action_taken: Mapped[str] = mapped_column(String(50), nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )

    __table_args__ = (
        CheckConstraint(
            "confidence_score >= 0.000 AND confidence_score <= 1.000",
            name="ck_intent_classifications_confidence",
        ),
        Index("ix_intent_classifications_email", "email_message_id"),
        Index("ix_intent_classifications_deal", "deal_id"),
        Index("ix_intent_classifications_intent", "intent"),
        Index("ix_intent_classifications_confidence", "confidence_score"),
        Index("ix_intent_classifications_action", "action_taken"),
        Index("ix_intent_classifications_created", "created_at"),
    )
