"""Deal ORM model - Cached HubSpot deal data."""

import uuid
from datetime import date, datetime
from decimal import Decimal

from sqlalchemy import Date, DateTime, ForeignKey, Index, Numeric, String
from sqlalchemy.dialects.postgresql import ARRAY, UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base, TimestampMixin, UUIDPrimaryKeyMixin


class Deal(Base, UUIDPrimaryKeyMixin, TimestampMixin):
    __tablename__ = "deals"

    hubspot_deal_id: Mapped[str] = mapped_column(String(50), unique=True, nullable=False)
    pipeline_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("pipeline_configs.id"), nullable=True
    )
    hubspot_pipeline_id: Mapped[str] = mapped_column(String(50), nullable=False)
    current_stage: Mapped[str] = mapped_column(String(50), nullable=False)
    current_stage_name: Mapped[str] = mapped_column(String(255), nullable=False)
    deal_name: Mapped[str] = mapped_column(String(500), nullable=False)
    owner_user_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("user_configs.id"), nullable=True
    )
    contact_ids: Mapped[list[uuid.UUID]] = mapped_column(
        ARRAY(UUID(as_uuid=True)), server_default="{}"
    )
    amount: Mapped[Decimal | None] = mapped_column(Numeric(15, 2), nullable=True)
    close_date: Mapped[date | None] = mapped_column(Date, nullable=True)
    last_synced_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)

    __table_args__ = (
        Index("ix_deals_owner_user_id", "owner_user_id"),
        Index("ix_deals_hubspot_pipeline_id", "hubspot_pipeline_id"),
        Index("ix_deals_current_stage", "current_stage"),
    )
