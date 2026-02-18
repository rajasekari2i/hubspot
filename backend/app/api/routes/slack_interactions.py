"""Slack interaction webhook handler - Processes button clicks from recommendation messages."""

import hashlib
import hmac
import json
import time
import uuid
from datetime import datetime, timedelta, timezone

import structlog
from fastapi import APIRouter, HTTPException, Request, status
from sqlalchemy import select

from app.config import get_settings
from app.dependencies import get_redis, get_session_factory
from app.integrations.hubspot.client import HubSpotClient
from app.integrations.slack.client import SlackClient
from app.models.audit_log import ActorType
from app.models.deal import Deal
from app.models.pipeline_config import PipelineConfig
from app.models.stage_recommendation import (
    RecommendationStatus,
    StageRecommendation,
    validate_transition,
)
from app.models.user_config import UserConfig
from app.services.audit import write_audit_log
from app.services.crm_updater import execute_crm_update
from app.services.notification import update_recommendation_message
from app.utils.rate_limiter import RateLimiter

logger = structlog.get_logger()

router = APIRouter(prefix="/slack", tags=["Webhooks"])


def _verify_slack_signature(
    body: bytes,
    timestamp: str,
    signature: str,
    signing_secret: str,
) -> bool:
    """Verify Slack request signature using X-Slack-Signature.

    Prevents replay attacks by rejecting timestamps older than 5 minutes.
    """
    # Reject requests older than 5 minutes
    if abs(time.time() - int(timestamp)) > 300:
        return False

    sig_basestring = f"v0:{timestamp}:{body.decode('utf-8')}"
    computed = "v0=" + hmac.new(
        signing_secret.encode("utf-8"),
        sig_basestring.encode("utf-8"),
        hashlib.sha256,
    ).hexdigest()

    return hmac.compare_digest(computed, signature)


@router.post("/interactions")
async def handle_slack_interaction(request: Request) -> dict:
    """Handle Slack interactive message callbacks (button clicks).

    Validates the request signature, parses the payload, and dispatches
    to the appropriate action handler.
    """
    settings = get_settings()

    # Read raw body for signature verification
    body = await request.body()
    timestamp = request.headers.get("X-Slack-Request-Timestamp", "")
    signature = request.headers.get("X-Slack-Signature", "")

    if not _verify_slack_signature(body, timestamp, signature, settings.slack_signing_secret):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid Slack signature",
        )

    # Parse the URL-encoded payload
    form_data = await request.form()
    payload_str = form_data.get("payload", "")
    if not payload_str:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Missing payload",
        )

    try:
        payload = json.loads(payload_str)
    except json.JSONDecodeError:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Invalid payload JSON",
        )

    payload_type = payload.get("type")
    if payload_type != "block_actions":
        return {"ok": True}

    actions = payload.get("actions", [])
    if not actions:
        return {"ok": True}

    action = actions[0]
    action_id = action.get("action_id", "")
    recommendation_id_str = action.get("value", "")
    slack_user = payload.get("user", {})
    slack_user_id = slack_user.get("id", "")
    slack_user_name = slack_user.get("name", slack_user.get("username", ""))

    if not recommendation_id_str:
        return {"ok": True}

    try:
        recommendation_id = uuid.UUID(recommendation_id_str)
    except ValueError:
        # For secondary actions, the value may be different
        recommendation_id_str = action.get("block_id", "").replace("block_", "")
        try:
            recommendation_id = uuid.UUID(recommendation_id_str)
        except ValueError:
            return {"text": "Invalid recommendation reference"}

    # Dispatch to action handlers
    handler_map = {
        "approve_recommendation": _handle_approve,
        "reject_recommendation": _handle_reject,
        "snooze_recommendation": _handle_snooze,
        "rejection_reason_selected": _handle_rejection_reason,
        "corrected_stage_selected": _handle_corrected_stage,
    }

    handler = handler_map.get(action_id)
    if not handler:
        await logger.awarn("unknown_slack_action", action_id=action_id)
        return {"ok": True}

    return await handler(recommendation_id, action, slack_user_id, slack_user_name, payload)


async def _handle_approve(
    recommendation_id: uuid.UUID,
    action: dict,
    slack_user_id: str,
    slack_user_name: str,
    payload: dict,
) -> dict:
    """Handle the Approve button click."""
    session_factory = get_session_factory()

    async with session_factory() as db:
        rec = await _get_rec(db, recommendation_id)
        if not rec:
            return {"text": "Recommendation not found"}

        if not validate_transition(rec.status, RecommendationStatus.APPROVED):
            return {"text": f"Cannot approve: already {rec.status.value}"}

        deal = await _get_deal(db, rec.deal_id)
        if not deal:
            return {"text": "Deal not found"}

        user = await _find_user_by_slack(db, slack_user_id)

        # Transition to approved
        rec.status = RecommendationStatus.APPROVED
        rec.reviewed_at = datetime.now(timezone.utc)
        rec.reviewed_by = user.id if user else None
        await db.flush()

        await write_audit_log(
            db,
            action="recommendation_approved",
            entity_type="stage_recommendation",
            entity_id=rec.id,
            actor_type=ActorType.USER,
            actor_id=str(user.id) if user else slack_user_id,
            before_state={"status": "pending"},
            after_state={"status": "approved"},
        )

        # Execute CRM update
        settings = get_settings()
        redis = await get_redis()
        rate_limiter = RateLimiter(redis, key_prefix="hubspot", max_tokens=8, window_seconds=1)
        hubspot_client = HubSpotClient(
            access_token=settings.hubspot_access_token,
            rate_limiter=rate_limiter,
        )

        crm_result = await execute_crm_update(
            db, hubspot_client, rec, deal,
            actor_id=str(user.id) if user else slack_user_id,
        )

        # Update Slack message
        slack_client = SlackClient(
            bot_token=settings.slack_bot_token,
            signing_secret=settings.slack_signing_secret,
        )
        status_text = "Approved" if crm_result.success else f"Approved (CRM: {crm_result.status.value})"
        await update_recommendation_message(
            slack_client, rec, deal,
            action_text=status_text,
            actor_name=slack_user_name,
        )

        await db.commit()

    return {"text": f"Recommendation approved by {slack_user_name}"}


async def _handle_reject(
    recommendation_id: uuid.UUID,
    action: dict,
    slack_user_id: str,
    slack_user_name: str,
    payload: dict,
) -> dict:
    """Handle the Reject button -- respond with rejection reason selector."""
    # Return a replacement message with reason selection
    blocks = [
        {
            "type": "section",
            "text": {
                "type": "mrkdwn",
                "text": "Please select a rejection reason:",
            },
        },
        {
            "type": "actions",
            "block_id": f"block_{recommendation_id}",
            "elements": [
                {
                    "type": "static_select",
                    "action_id": "rejection_reason_selected",
                    "placeholder": {"type": "plain_text", "text": "Select reason..."},
                    "options": [
                        {"text": {"type": "plain_text", "text": "Wrong Stage"}, "value": f"{recommendation_id}|wrong_stage"},
                        {"text": {"type": "plain_text", "text": "Wrong Deal"}, "value": f"{recommendation_id}|wrong_deal"},
                        {"text": {"type": "plain_text", "text": "Not Relevant"}, "value": f"{recommendation_id}|not_relevant"},
                        {"text": {"type": "plain_text", "text": "Other"}, "value": f"{recommendation_id}|other"},
                    ],
                },
            ],
        },
    ]

    return {"replace_original": True, "blocks": blocks}


async def _handle_rejection_reason(
    recommendation_id: uuid.UUID,
    action: dict,
    slack_user_id: str,
    slack_user_name: str,
    payload: dict,
) -> dict:
    """Handle rejection reason selection from the dropdown."""
    selected = action.get("selected_option", {}).get("value", "")
    parts = selected.split("|", 1)
    if len(parts) != 2:
        return {"text": "Invalid selection"}

    rec_id_str, reason = parts
    try:
        rec_id = uuid.UUID(rec_id_str)
    except ValueError:
        return {"text": "Invalid recommendation ID"}

    session_factory = get_session_factory()

    async with session_factory() as db:
        rec = await _get_rec(db, rec_id)
        if not rec:
            return {"text": "Recommendation not found"}

        if not validate_transition(rec.status, RecommendationStatus.REJECTED):
            return {"text": f"Cannot reject: already {rec.status.value}"}

        deal = await _get_deal(db, rec.deal_id)
        if not deal:
            return {"text": "Deal not found"}

        user = await _find_user_by_slack(db, slack_user_id)

        rec.status = RecommendationStatus.REJECTED
        rec.reviewed_at = datetime.now(timezone.utc)
        rec.reviewed_by = user.id if user else None
        rec.rejection_reason = reason
        await db.flush()

        await write_audit_log(
            db,
            action="recommendation_rejected",
            entity_type="stage_recommendation",
            entity_id=rec.id,
            actor_type=ActorType.USER,
            actor_id=str(user.id) if user else slack_user_id,
            before_state={"status": "pending"},
            after_state={"status": "rejected", "reason": reason},
        )

        # Update Slack message
        settings = get_settings()
        slack_client = SlackClient(
            bot_token=settings.slack_bot_token,
            signing_secret=settings.slack_signing_secret,
        )
        await update_recommendation_message(
            slack_client, rec, deal,
            action_text=f"Rejected ({reason})",
            actor_name=slack_user_name,
        )

        await db.commit()

    return {"text": f"Recommendation rejected ({reason}) by {slack_user_name}"}


async def _handle_snooze(
    recommendation_id: uuid.UUID,
    action: dict,
    slack_user_id: str,
    slack_user_name: str,
    payload: dict,
) -> dict:
    """Handle the Snooze button click."""
    session_factory = get_session_factory()

    async with session_factory() as db:
        rec = await _get_rec(db, recommendation_id)
        if not rec:
            return {"text": "Recommendation not found"}

        if not validate_transition(rec.status, RecommendationStatus.SNOOZED):
            return {"text": f"Cannot snooze: already {rec.status.value}"}

        # Check max snoozes
        deal = await _get_deal(db, rec.deal_id)
        if not deal:
            return {"text": "Deal not found"}

        pipeline_result = await db.execute(
            select(PipelineConfig).where(
                PipelineConfig.hubspot_pipeline_id == deal.hubspot_pipeline_id,
                PipelineConfig.is_active.is_(True),
            )
        )
        pipeline_config = pipeline_result.scalar_one_or_none()
        max_snoozes = pipeline_config.max_snoozes if pipeline_config else 2

        if rec.snooze_count >= max_snoozes:
            return {"text": f"Max snoozes ({max_snoozes}) reached. Please approve or reject."}

        user = await _find_user_by_slack(db, slack_user_id)

        rec.status = RecommendationStatus.SNOOZED
        rec.snooze_count += 1
        rec.expires_at = datetime.now(timezone.utc) + timedelta(hours=24)
        await db.flush()

        await write_audit_log(
            db,
            action="recommendation_snoozed",
            entity_type="stage_recommendation",
            entity_id=rec.id,
            actor_type=ActorType.USER,
            actor_id=str(user.id) if user else slack_user_id,
            after_state={
                "status": "snoozed",
                "snooze_count": rec.snooze_count,
            },
        )

        # Update Slack message
        settings = get_settings()
        slack_client = SlackClient(
            bot_token=settings.slack_bot_token,
            signing_secret=settings.slack_signing_secret,
        )
        await update_recommendation_message(
            slack_client, rec, deal,
            action_text=f"Snoozed (24h) [{rec.snooze_count}/{max_snoozes}]",
            actor_name=slack_user_name,
        )

        await db.commit()

    return {"text": f"Snoozed for 24h by {slack_user_name} ({rec.snooze_count}/{max_snoozes})"}


async def _handle_corrected_stage(
    recommendation_id: uuid.UUID,
    action: dict,
    slack_user_id: str,
    slack_user_name: str,
    payload: dict,
) -> dict:
    """Handle corrected stage selection after rejection."""
    selected_stage = action.get("selected_option", {}).get("value", "")
    if not selected_stage:
        return {"text": "No stage selected"}

    session_factory = get_session_factory()

    async with session_factory() as db:
        rec = await _get_rec(db, recommendation_id)
        if not rec:
            return {"text": "Recommendation not found"}

        rec.user_corrected_stage = selected_stage
        await db.flush()
        await db.commit()

    return {"text": f"Corrected stage set to {selected_stage}"}


# ---------- Shared helpers ----------


async def _get_rec(db, rec_id: uuid.UUID) -> StageRecommendation | None:
    result = await db.execute(
        select(StageRecommendation).where(StageRecommendation.id == rec_id)
    )
    return result.scalar_one_or_none()


async def _get_deal(db, deal_id: uuid.UUID) -> Deal | None:
    result = await db.execute(select(Deal).where(Deal.id == deal_id))
    return result.scalar_one_or_none()


async def _find_user_by_slack(db, slack_user_id: str) -> UserConfig | None:
    result = await db.execute(
        select(UserConfig).where(UserConfig.slack_user_id == slack_user_id)
    )
    return result.scalar_one_or_none()
