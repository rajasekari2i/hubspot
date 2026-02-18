"""Credential ORM model - Encrypted OAuth tokens for external services."""

import enum
import uuid

from sqlalchemy import DateTime, Enum, ForeignKey, Index, LargeBinary, UniqueConstraint
from sqlalchemy.dialects.postgresql import ARRAY, UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship
from sqlalchemy import String

from app.models.base import Base, TimestampMixin, UUIDPrimaryKeyMixin


class ProviderType(str, enum.Enum):
    GMAIL = "gmail"
    HUBSPOT = "hubspot"
    SLACK = "slack"


class Credential(Base, UUIDPrimaryKeyMixin, TimestampMixin):
    __tablename__ = "credentials"

    user_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("user_configs.id"), nullable=False
    )
    provider: Mapped[ProviderType] = mapped_column(Enum(ProviderType), nullable=False)
    access_token_enc: Mapped[bytes] = mapped_column(LargeBinary, nullable=False)
    refresh_token_enc: Mapped[bytes | None] = mapped_column(LargeBinary, nullable=True)
    token_expiry: Mapped[str] = mapped_column(DateTime(timezone=True), nullable=False)
    scopes: Mapped[list[str]] = mapped_column(ARRAY(String), nullable=False)

    # Relationships
    user = relationship("UserConfig", back_populates="credentials")

    __table_args__ = (
        UniqueConstraint("user_id", "provider", name="uq_credentials_user_provider"),
        Index("ix_credentials_user_id", "user_id"),
        Index("ix_credentials_token_expiry", "token_expiry"),
    )
