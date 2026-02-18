"""US1 email and classification models.

Revision ID: 002
Revises: 001
Create Date: 2026-02-15
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

revision: str = "002"
down_revision: Union[str, None] = "001"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # email_messages
    op.create_table(
        "email_messages",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("gmail_message_id", sa.String(50), unique=True, nullable=False),
        sa.Column("gmail_thread_id", sa.String(50), nullable=False),
        sa.Column("gmail_history_id", sa.BigInteger, nullable=False),
        sa.Column("user_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("from_address", sa.String(255), nullable=False),
        sa.Column("to_addresses", postgresql.ARRAY(sa.String), nullable=False),
        sa.Column("cc_addresses", postgresql.ARRAY(sa.String), server_default="{}"),
        sa.Column("subject", sa.String(500), nullable=False),
        sa.Column("body_excerpt", sa.String(500), nullable=True),
        sa.Column("received_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("processed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column(
            "processing_status",
            sa.Enum("pending", "processing", "classified", "failed", name="processingstatus"),
            server_default="pending",
            nullable=False,
        ),
        sa.Column("trace_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
    )
    op.create_index("ix_email_messages_gmail_thread_id", "email_messages", ["gmail_thread_id"])
    op.create_index("ix_email_messages_user_received", "email_messages", ["user_id", "received_at"])
    op.create_index("ix_email_messages_processing_status", "email_messages", ["processing_status"])
    op.create_index("ix_email_messages_trace_id", "email_messages", ["trace_id"])

    # email_threads
    op.create_table(
        "email_threads",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("gmail_thread_id", sa.String(50), unique=True, nullable=False),
        sa.Column("deal_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("deals.id"), nullable=True),
        sa.Column("contact_ids", postgresql.ARRAY(postgresql.UUID(as_uuid=True)), server_default="{}"),
        sa.Column("subject", sa.String(500), nullable=True),
        sa.Column("message_count", sa.Integer, server_default="0"),
        sa.Column("last_activity_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("link_confidence", sa.Numeric(4, 3), nullable=True),
        sa.Column("link_method", sa.String(50), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
    )
    op.create_index("ix_email_threads_deal_id", "email_threads", ["deal_id"])

    # intent_classifications
    op.create_table(
        "intent_classifications",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("email_message_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("email_messages.id"), nullable=False),
        sa.Column("deal_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("deals.id"), nullable=True),
        sa.Column("intent", sa.String(50), nullable=False),
        sa.Column("confidence_score", sa.Numeric(4, 3), nullable=False),
        sa.Column("reasoning", sa.Text, nullable=False),
        sa.Column("key_phrases", postgresql.ARRAY(sa.String), server_default="{}"),
        sa.Column("direction", sa.Enum("forward", "backward", "neutral", name="direction"), nullable=False),
        sa.Column("prompt_version", sa.String(20), nullable=False),
        sa.Column("llm_model", sa.String(50), nullable=False),
        sa.Column("llm_latency_ms", sa.Integer, nullable=False),
        sa.Column("input_tokens", sa.Integer, nullable=True),
        sa.Column("output_tokens", sa.Integer, nullable=True),
        sa.Column("action_taken", sa.String(50), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.CheckConstraint("confidence_score >= 0.000 AND confidence_score <= 1.000", name="ck_intent_classifications_confidence"),
    )
    op.create_index("ix_intent_classifications_email", "intent_classifications", ["email_message_id"])
    op.create_index("ix_intent_classifications_deal", "intent_classifications", ["deal_id"])
    op.create_index("ix_intent_classifications_intent", "intent_classifications", ["intent"])
    op.create_index("ix_intent_classifications_confidence", "intent_classifications", ["confidence_score"])
    op.create_index("ix_intent_classifications_action", "intent_classifications", ["action_taken"])
    op.create_index("ix_intent_classifications_created", "intent_classifications", ["created_at"])

    # stage_recommendations
    op.create_table(
        "stage_recommendations",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("email_message_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("email_messages.id"), nullable=False),
        sa.Column("thread_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("email_threads.id"), nullable=False),
        sa.Column("deal_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("deals.id"), nullable=False),
        sa.Column("current_stage", sa.String(50), nullable=False),
        sa.Column("recommended_stage", sa.String(50), nullable=False),
        sa.Column("recommended_stage_name", sa.String(255), nullable=False),
        sa.Column("confidence_score", sa.Numeric(4, 3), nullable=False),
        sa.Column("intent", sa.String(50), nullable=False),
        sa.Column("reasoning", sa.Text, nullable=False),
        sa.Column("key_phrases", postgresql.ARRAY(sa.String), server_default="{}"),
        sa.Column("direction", sa.Enum("forward", "backward", "neutral", name="direction", create_type=False), nullable=False),
        sa.Column("prompt_version", sa.String(20), nullable=False),
        sa.Column("llm_model", sa.String(50), nullable=False),
        sa.Column("llm_latency_ms", sa.Integer, nullable=True),
        sa.Column(
            "status",
            sa.Enum("pending", "approved", "rejected", "expired", "superseded", "snoozed", "write_success", "write_failed", "conflict", name="recommendationstatus"),
            server_default="pending",
            nullable=False,
        ),
        sa.Column("reviewed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("reviewed_by", postgresql.UUID(as_uuid=True), sa.ForeignKey("user_configs.id"), nullable=True),
        sa.Column("rejection_reason", sa.String(50), nullable=True),
        sa.Column("user_corrected_stage", sa.String(50), nullable=True),
        sa.Column("slack_message_ts", sa.String(50), nullable=True),
        sa.Column("slack_channel_id", sa.String(50), nullable=True),
        sa.Column("snooze_count", sa.Integer, server_default="0"),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("idempotency_key", sa.String(100), unique=True, nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.CheckConstraint("confidence_score >= 0.000 AND confidence_score <= 1.000", name="ck_stage_recommendations_confidence"),
    )
    op.create_index("ix_stage_recommendations_deal_status", "stage_recommendations", ["deal_id", "status"])
    op.create_index("ix_stage_recommendations_status_expires", "stage_recommendations", ["status", "expires_at"])
    op.create_index("ix_stage_recommendations_reviewed_by", "stage_recommendations", ["reviewed_by"])
    op.create_index("ix_stage_recommendations_created_at", "stage_recommendations", ["created_at"])


def downgrade() -> None:
    op.drop_table("stage_recommendations")
    op.drop_table("intent_classifications")
    op.drop_table("email_threads")
    op.drop_table("email_messages")
    op.execute("DROP TYPE IF EXISTS processingstatus")
    op.execute("DROP TYPE IF EXISTS direction")
    op.execute("DROP TYPE IF EXISTS recommendationstatus")
