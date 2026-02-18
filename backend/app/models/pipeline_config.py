"""PipelineConfig ORM model - HubSpot pipeline mapping rules."""

from decimal import Decimal

from sqlalchemy import Boolean, Integer, Numeric, String, Index
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base, TimestampMixin, UUIDPrimaryKeyMixin


class PipelineConfig(Base, UUIDPrimaryKeyMixin, TimestampMixin):
    __tablename__ = "pipeline_configs"

    hubspot_pipeline_id: Mapped[str] = mapped_column(
        String(50), unique=True, nullable=False
    )
    pipeline_name: Mapped[str] = mapped_column(String(255), nullable=False)
    stages: Mapped[dict] = mapped_column(JSONB, nullable=False)
    intent_to_stage_rules: Mapped[dict] = mapped_column(JSONB, nullable=False)
    stage_ordering: Mapped[dict] = mapped_column(JSONB, nullable=False)
    is_active: Mapped[bool] = mapped_column(Boolean, server_default="true")
    recommendation_threshold: Mapped[Decimal] = mapped_column(
        Numeric(4, 3), server_default="0.700"
    )
    logging_threshold: Mapped[Decimal] = mapped_column(
        Numeric(4, 3), server_default="0.300"
    )
    approval_timeout_hours: Mapped[int] = mapped_column(Integer, server_default="48")
    max_snoozes: Mapped[int] = mapped_column(Integer, server_default="2")

    __table_args__ = (Index("ix_pipeline_configs_is_active", "is_active"),)
