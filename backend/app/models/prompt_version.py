"""PromptVersion ORM model - Versioned LLM classification prompts."""

import uuid

from sqlalchemy import Boolean, ForeignKey, Index, String, Text
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base, UUIDPrimaryKeyMixin
from sqlalchemy import DateTime, func
from datetime import datetime


class PromptVersion(Base, UUIDPrimaryKeyMixin):
    __tablename__ = "prompt_versions"

    version: Mapped[str] = mapped_column(String(20), unique=True, nullable=False)
    prompt_template: Mapped[str] = mapped_column(Text, nullable=False)
    system_prompt: Mapped[str] = mapped_column(Text, nullable=False)
    intent_categories: Mapped[dict] = mapped_column(JSONB, nullable=False)
    is_active: Mapped[bool] = mapped_column(Boolean, server_default="false")
    created_by: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("user_configs.id"), nullable=True
    )
    notes: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )

    __table_args__ = (
        # Partial unique index: only one active prompt at a time
        Index(
            "ix_prompt_versions_active_unique",
            "is_active",
            unique=True,
            postgresql_where=(is_active.is_(True)),  # type: ignore[attr-defined]
        ),
    )
