"""UserConfig ORM model - System user profiles with linked external accounts."""

import enum

from sqlalchemy import Boolean, BigInteger, DateTime, Enum, Index, String
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import Base, TimestampMixin, UUIDPrimaryKeyMixin


class UserRole(str, enum.Enum):
    ADMIN = "admin"
    REVOPS = "revops"
    SALES_USER = "sales_user"


class UserConfig(Base, UUIDPrimaryKeyMixin, TimestampMixin):
    __tablename__ = "user_configs"

    email: Mapped[str] = mapped_column(String(255), unique=True, nullable=False)
    display_name: Mapped[str] = mapped_column(String(255), nullable=False)
    role: Mapped[UserRole] = mapped_column(Enum(UserRole), nullable=False)
    hubspot_user_id: Mapped[str | None] = mapped_column(String(50), nullable=True)
    hubspot_owner_id: Mapped[str | None] = mapped_column(String(50), nullable=True, index=True)
    slack_user_id: Mapped[str | None] = mapped_column(String(50), nullable=True)
    gmail_watch_expiration: Mapped[str | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    gmail_last_history_id: Mapped[int | None] = mapped_column(BigInteger, nullable=True)
    notification_channel: Mapped[str] = mapped_column(String(20), server_default="slack")
    is_active: Mapped[bool] = mapped_column(Boolean, server_default="true")

    # Relationships
    credentials = relationship("Credential", back_populates="user", lazy="selectin")

    __table_args__ = (Index("ix_user_configs_is_active", "is_active"),)
