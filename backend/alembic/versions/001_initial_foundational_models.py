"""Initial foundational models.

Revision ID: 001
Revises:
Create Date: 2026-02-15
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

revision: str = "001"
down_revision: Union[str, None] = None
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # user_configs
    op.create_table(
        "user_configs",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("email", sa.String(255), unique=True, nullable=False),
        sa.Column("display_name", sa.String(255), nullable=False),
        sa.Column("role", sa.Enum("admin", "revops", "sales_user", name="userrole"), nullable=False),
        sa.Column("hubspot_user_id", sa.String(50), nullable=True),
        sa.Column("hubspot_owner_id", sa.String(50), nullable=True),
        sa.Column("slack_user_id", sa.String(50), nullable=True),
        sa.Column("gmail_watch_expiration", sa.DateTime(timezone=True), nullable=True),
        sa.Column("gmail_last_history_id", sa.BigInteger, nullable=True),
        sa.Column("notification_channel", sa.String(20), server_default="slack"),
        sa.Column("is_active", sa.Boolean, server_default="true"),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
    )
    op.create_index("ix_user_configs_hubspot_owner_id", "user_configs", ["hubspot_owner_id"])
    op.create_index("ix_user_configs_is_active", "user_configs", ["is_active"])

    # credentials
    op.create_table(
        "credentials",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("user_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("user_configs.id"), nullable=False),
        sa.Column("provider", sa.Enum("gmail", "hubspot", "slack", name="providertype"), nullable=False),
        sa.Column("access_token_enc", sa.LargeBinary, nullable=False),
        sa.Column("refresh_token_enc", sa.LargeBinary, nullable=True),
        sa.Column("token_expiry", sa.DateTime(timezone=True), nullable=False),
        sa.Column("scopes", postgresql.ARRAY(sa.String), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.UniqueConstraint("user_id", "provider", name="uq_credentials_user_provider"),
    )
    op.create_index("ix_credentials_user_id", "credentials", ["user_id"])
    op.create_index("ix_credentials_token_expiry", "credentials", ["token_expiry"])

    # pipeline_configs
    op.create_table(
        "pipeline_configs",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("hubspot_pipeline_id", sa.String(50), unique=True, nullable=False),
        sa.Column("pipeline_name", sa.String(255), nullable=False),
        sa.Column("stages", postgresql.JSONB, nullable=False),
        sa.Column("intent_to_stage_rules", postgresql.JSONB, nullable=False),
        sa.Column("stage_ordering", postgresql.JSONB, nullable=False),
        sa.Column("is_active", sa.Boolean, server_default="true"),
        sa.Column("recommendation_threshold", sa.Numeric(4, 3), server_default="0.700"),
        sa.Column("logging_threshold", sa.Numeric(4, 3), server_default="0.300"),
        sa.Column("approval_timeout_hours", sa.Integer, server_default="48"),
        sa.Column("max_snoozes", sa.Integer, server_default="2"),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
    )
    op.create_index("ix_pipeline_configs_is_active", "pipeline_configs", ["is_active"])

    # prompt_versions
    op.create_table(
        "prompt_versions",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("version", sa.String(20), unique=True, nullable=False),
        sa.Column("prompt_template", sa.Text, nullable=False),
        sa.Column("system_prompt", sa.Text, nullable=False),
        sa.Column("intent_categories", postgresql.JSONB, nullable=False),
        sa.Column("is_active", sa.Boolean, server_default="false"),
        sa.Column("created_by", postgresql.UUID(as_uuid=True), sa.ForeignKey("user_configs.id"), nullable=True),
        sa.Column("notes", sa.Text, nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
    )

    # deals
    op.create_table(
        "deals",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("hubspot_deal_id", sa.String(50), unique=True, nullable=False),
        sa.Column("pipeline_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("pipeline_configs.id"), nullable=True),
        sa.Column("hubspot_pipeline_id", sa.String(50), nullable=False),
        sa.Column("current_stage", sa.String(50), nullable=False),
        sa.Column("current_stage_name", sa.String(255), nullable=False),
        sa.Column("deal_name", sa.String(500), nullable=False),
        sa.Column("owner_user_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("user_configs.id"), nullable=True),
        sa.Column("contact_ids", postgresql.ARRAY(postgresql.UUID(as_uuid=True)), server_default="{}"),
        sa.Column("amount", sa.Numeric(15, 2), nullable=True),
        sa.Column("close_date", sa.Date, nullable=True),
        sa.Column("last_synced_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
    )
    op.create_index("ix_deals_owner_user_id", "deals", ["owner_user_id"])
    op.create_index("ix_deals_hubspot_pipeline_id", "deals", ["hubspot_pipeline_id"])
    op.create_index("ix_deals_current_stage", "deals", ["current_stage"])

    # audit_logs
    op.create_table(
        "audit_logs",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("trace_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("action", sa.String(100), nullable=False),
        sa.Column("entity_type", sa.String(50), nullable=False),
        sa.Column("entity_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("actor_type", sa.Enum("system", "user", name="actortype"), nullable=False),
        sa.Column("actor_id", sa.String(100), nullable=True),
        sa.Column("before_state", postgresql.JSONB, nullable=True),
        sa.Column("after_state", postgresql.JSONB, nullable=True),
        sa.Column("metadata", postgresql.JSONB, server_default="{}"),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
    )
    op.create_index("ix_audit_logs_entity", "audit_logs", ["entity_type", "entity_id"])
    op.create_index("ix_audit_logs_action", "audit_logs", ["action"])
    op.create_index("ix_audit_logs_actor_id", "audit_logs", ["actor_id"])
    op.create_index("ix_audit_logs_created_at", "audit_logs", ["created_at"])
    op.create_index("ix_audit_logs_trace_id", "audit_logs", ["trace_id"])

    # dead_messages
    op.create_table(
        "dead_messages",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("component", sa.String(50), nullable=False),
        sa.Column("original_payload", postgresql.JSONB, nullable=False),
        sa.Column("error_message", sa.Text, nullable=False),
        sa.Column("retry_count", sa.Integer, nullable=False),
        sa.Column("trace_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("first_failed_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("last_failed_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("resolved", sa.Boolean, server_default="false"),
        sa.Column("resolved_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("resolved_by", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
    )
    op.create_index("ix_dead_messages_component", "dead_messages", ["component"])
    op.create_index("ix_dead_messages_resolved", "dead_messages", ["resolved"])
    op.create_index("ix_dead_messages_first_failed_at", "dead_messages", ["first_failed_at"])


def downgrade() -> None:
    op.drop_table("dead_messages")
    op.drop_table("audit_logs")
    op.drop_table("deals")
    op.drop_table("prompt_versions")
    op.drop_table("pipeline_configs")
    op.drop_table("credentials")
    op.drop_table("user_configs")
    op.execute("DROP TYPE IF EXISTS userrole")
    op.execute("DROP TYPE IF EXISTS providertype")
    op.execute("DROP TYPE IF EXISTS actortype")
