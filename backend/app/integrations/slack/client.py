"""Slack messaging integration for pipeline recommendations and alerts."""

from __future__ import annotations

from typing import Any

import structlog
from slack_sdk.web.async_client import AsyncWebClient

from app.integrations.slack.protocol import MessagingProvider
from app.utils.circuit_breaker import circuit_breaker

logger = structlog.get_logger(__name__)


class SlackClient(MessagingProvider):
    """Messaging provider implementation using the Slack async SDK."""

    def __init__(self, bot_token: str, signing_secret: str) -> None:
        self._client = AsyncWebClient(token=bot_token)
        self._signing_secret = signing_secret
        logger.info("slack_client_initialized")

    @staticmethod
    def _confidence_emoji(score: float) -> str:
        """Return a color-coded circle emoji based on confidence score.

        Args:
            score: Confidence score between 0 and 1.

        Returns:
            A green, yellow, or red circle emoji string.
        """
        if score > 0.85:
            return ":large_green_circle:"
        if score > 0.7:
            return ":large_yellow_circle:"
        return ":red_circle:"

    @staticmethod
    def _build_recommendation_blocks(
        recommendation_data: dict[str, Any],
    ) -> list[dict[str, Any]]:
        """Build Slack Block Kit blocks for a stage-change recommendation.

        Constructs a structured message containing a header, deal details,
        confidence context, and action buttons for approval workflow.

        Args:
            recommendation_data: Dictionary containing recommendation details
                with keys: deal_name, current_stage, recommended_stage,
                confidence_score, intent, reasoning, recommendation_id.

        Returns:
            A list of Block Kit block dictionaries ready for Slack API.
        """
        deal_name = recommendation_data["deal_name"]
        current_stage = recommendation_data["current_stage"]
        recommended_stage = recommendation_data["recommended_stage"]
        confidence_score = float(recommendation_data["confidence_score"])
        intent = recommendation_data["intent"]
        reasoning = recommendation_data["reasoning"]
        recommendation_id = str(recommendation_data["recommendation_id"])

        confidence_emoji = SlackClient._confidence_emoji(confidence_score)

        blocks: list[dict[str, Any]] = [
            {
                "type": "header",
                "text": {
                    "type": "plain_text",
                    "text": "Stage Change Recommendation",
                    "emoji": True,
                },
            },
            {
                "type": "section",
                "fields": [
                    {
                        "type": "mrkdwn",
                        "text": f"*Deal:*\n{deal_name}",
                    },
                    {
                        "type": "mrkdwn",
                        "text": (
                            f"*Stage Change:*\n"
                            f"{current_stage} :arrow_right: {recommended_stage}"
                        ),
                    },
                ],
            },
            {
                "type": "context",
                "elements": [
                    {
                        "type": "mrkdwn",
                        "text": (
                            f"{confidence_emoji} *Confidence:* "
                            f"{confidence_score:.0%}  |  "
                            f"*Intent:* {intent}"
                        ),
                    },
                    {
                        "type": "mrkdwn",
                        "text": f"*Reasoning:* {reasoning}",
                    },
                ],
            },
            {"type": "divider"},
            {
                "type": "actions",
                "elements": [
                    {
                        "type": "button",
                        "text": {
                            "type": "plain_text",
                            "text": "Approve",
                            "emoji": True,
                        },
                        "style": "primary",
                        "action_id": "approve_recommendation",
                        "value": recommendation_id,
                    },
                    {
                        "type": "button",
                        "text": {
                            "type": "plain_text",
                            "text": "Reject",
                            "emoji": True,
                        },
                        "style": "danger",
                        "action_id": "reject_recommendation",
                        "value": recommendation_id,
                    },
                    {
                        "type": "button",
                        "text": {
                            "type": "plain_text",
                            "text": "Snooze 24h",
                            "emoji": True,
                        },
                        "action_id": "snooze_recommendation",
                        "value": recommendation_id,
                    },
                ],
            },
        ]

        return blocks

    @circuit_breaker(name="slack", failure_threshold=5, reset_timeout=60)
    async def send_recommendation(
        self,
        channel_or_user: str,
        recommendation_data: dict[str, Any],
    ) -> dict[str, Any]:
        """Send a stage-change recommendation message to Slack.

        Builds a Block Kit message with deal details, confidence indicators,
        and approve/reject/snooze action buttons, then posts it to the
        specified channel or user.

        Args:
            channel_or_user: The Slack channel ID or user ID to send to.
            recommendation_data: Dictionary with keys: deal_name,
                current_stage, recommended_stage, confidence_score, intent,
                reasoning, recommendation_id.

        Returns:
            A dict with channel, ts (timestamp), and ok status.

        Raises:
            slack_sdk.errors.SlackApiError: If the Slack API returns an error.
        """
        blocks = self._build_recommendation_blocks(recommendation_data)
        fallback_text = (
            f"Stage Change Recommendation for "
            f"{recommendation_data['deal_name']}: "
            f"{recommendation_data['current_stage']} -> "
            f"{recommendation_data['recommended_stage']}"
        )

        logger.info(
            "slack_send_recommendation",
            channel=channel_or_user,
            deal=recommendation_data.get("deal_name"),
            recommendation_id=recommendation_data.get("recommendation_id"),
        )

        response = await self._client.chat_postMessage(
            channel=channel_or_user,
            text=fallback_text,
            blocks=blocks,
        )

        logger.info(
            "slack_send_recommendation_success",
            channel=response["channel"],
            ts=response["ts"],
        )

        return {
            "channel": response["channel"],
            "ts": response["ts"],
            "ok": True,
        }

    @circuit_breaker(name="slack", failure_threshold=5, reset_timeout=60)
    async def update_message(
        self,
        channel: str,
        message_ts: str,
        updated_blocks: list[dict[str, Any]],
    ) -> dict[str, Any]:
        """Update an existing Slack message with new blocks.

        Args:
            channel: The Slack channel ID containing the message.
            message_ts: The timestamp of the message to update.
            updated_blocks: The new Block Kit blocks to replace the current
                message content.

        Returns:
            The raw Slack API response as a dict.

        Raises:
            slack_sdk.errors.SlackApiError: If the Slack API returns an error.
        """
        logger.info(
            "slack_update_message",
            channel=channel,
            message_ts=message_ts,
        )

        response = await self._client.chat_update(
            channel=channel,
            ts=message_ts,
            blocks=updated_blocks,
        )

        logger.info(
            "slack_update_message_success",
            channel=response["channel"],
            ts=response["ts"],
        )

        return dict(response)

    @circuit_breaker(name="slack", failure_threshold=5, reset_timeout=60)
    async def send_alert(
        self,
        channel: str,
        text: str,
    ) -> dict[str, Any]:
        """Send a simple text alert to a Slack channel.

        Args:
            channel: The Slack channel ID to send the alert to.
            text: The plain text message content.

        Returns:
            The raw Slack API response as a dict.

        Raises:
            slack_sdk.errors.SlackApiError: If the Slack API returns an error.
        """
        logger.info("slack_send_alert", channel=channel)

        response = await self._client.chat_postMessage(
            channel=channel,
            text=text,
        )

        logger.info(
            "slack_send_alert_success",
            channel=response["channel"],
            ts=response["ts"],
        )

        return dict(response)

    @circuit_breaker(name="slack", failure_threshold=5, reset_timeout=60)
    async def health_check(self) -> bool:
        """Check connectivity to the Slack API.

        Calls the auth.test endpoint to verify that the bot token is valid
        and the Slack workspace is reachable.

        Returns:
            True if authentication succeeds, False otherwise.
        """
        try:
            response = await self._client.auth_test()
            logger.debug(
                "slack_health_check_ok",
                team=response.get("team"),
                user=response.get("user"),
            )
            return True
        except Exception as exc:
            logger.warning("slack_health_check_failed", error=str(exc))
            return False
