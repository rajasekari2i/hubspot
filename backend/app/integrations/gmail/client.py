"""Gmail API client implementing EmailProvider protocol.

Uses google-api-python-client to interact with the Gmail API,
with circuit breaker, retry, and async wrappers.
"""

from __future__ import annotations

import asyncio
from typing import Any

import structlog
from google.oauth2.credentials import Credentials
from googleapiclient.discovery import build

from app.integrations.gmail.protocol import EmailProvider
from app.utils.circuit_breaker import CircuitBreaker
from app.utils.retry import retry_with_backoff

logger = structlog.get_logger(__name__)

circuit_breaker = CircuitBreaker(
    name="gmail",
    failure_threshold=5,
    reset_timeout=60,
)


class GmailClient(EmailProvider):
    """Gmail API client with circuit breaker and retry support.

    All public methods are async and use ``asyncio.to_thread`` to delegate
    the synchronous Google API calls to a thread-pool executor so they
    never block the event loop.
    """

    def __init__(self, credentials: dict[str, Any], project_id: str) -> None:
        self._project_id = project_id
        self._credentials = credentials
        self._creds = Credentials(
            token=credentials.get("token"),
            refresh_token=credentials.get("refresh_token"),
            token_uri=credentials.get("token_uri", "https://oauth2.googleapis.com/token"),
            client_id=credentials.get("client_id"),
            client_secret=credentials.get("client_secret"),
        )
        self._service = build("gmail", "v1", credentials=self._creds)
        logger.info("gmail_client.initialized", project_id=project_id)

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    def _pubsub_topic(self) -> str:
        return f"projects/{self._project_id}/topics/gmail-push-notifications"

    def _build_watch_request(self, user_email: str) -> dict[str, Any]:
        return {
            "topicName": self._pubsub_topic(),
            "labelIds": ["INBOX"],
        }

    @staticmethod
    def _extract_header(headers: list[dict[str, str]], name: str) -> str:
        """Return the value of the first header matching *name* (case-insensitive)."""
        for header in headers:
            if header.get("name", "").lower() == name.lower():
                return header.get("value", "")
        return ""

    @staticmethod
    def _split_addresses(raw: str) -> list[str]:
        """Split a comma-separated address string into a cleaned list."""
        if not raw:
            return []
        return [addr.strip() for addr in raw.split(",") if addr.strip()]

    # ------------------------------------------------------------------
    # EmailProvider interface
    # ------------------------------------------------------------------

    @retry_with_backoff
    @circuit_breaker
    async def setup_watch(self, user_email: str) -> dict[str, Any]:
        """Register a Gmail push-notification watch via Pub/Sub.

        Returns the watch response containing ``historyId`` and
        ``expiration``.
        """
        logger.info("gmail_client.setup_watch", user_email=user_email)

        body = self._build_watch_request(user_email)

        def _call() -> dict[str, Any]:
            return (
                self._service.users()
                .watch(userId=user_email, body=body)
                .execute()
            )

        response: dict[str, Any] = await asyncio.to_thread(_call)

        logger.info(
            "gmail_client.watch_established",
            user_email=user_email,
            history_id=response.get("historyId"),
            expiration=response.get("expiration"),
        )
        return response

    @retry_with_backoff
    @circuit_breaker
    async def get_history(
        self, user_email: str, start_history_id: str
    ) -> list[str]:
        """Return message IDs added since *start_history_id*."""
        logger.info(
            "gmail_client.get_history",
            user_email=user_email,
            start_history_id=start_history_id,
        )

        def _call() -> dict[str, Any]:
            return (
                self._service.users()
                .history()
                .list(
                    userId=user_email,
                    startHistoryId=start_history_id,
                    historyTypes=["messageAdded"],
                )
                .execute()
            )

        response: dict[str, Any] = await asyncio.to_thread(_call)

        added_ids: list[str] = []
        for record in response.get("history", []):
            for msg_added in record.get("messagesAdded", []):
                msg = msg_added.get("message", {})
                msg_id = msg.get("id")
                if msg_id:
                    added_ids.append(msg_id)

        logger.info(
            "gmail_client.history_fetched",
            user_email=user_email,
            added_count=len(added_ids),
        )
        return added_ids

    @retry_with_backoff
    @circuit_breaker
    async def get_message(
        self, user_email: str, message_id: str
    ) -> dict[str, Any]:
        """Fetch a single message's metadata and return a clean dict.

        Returned keys: ``from_address``, ``to_addresses``, ``cc_addresses``,
        ``subject``, ``date``, ``gmail_thread_id``, ``snippet``.
        """
        logger.info(
            "gmail_client.get_message",
            user_email=user_email,
            message_id=message_id,
        )

        def _call() -> dict[str, Any]:
            return (
                self._service.users()
                .messages()
                .get(
                    userId=user_email,
                    id=message_id,
                    format="metadata",
                    metadataHeaders=["From", "To", "Cc", "Subject", "Date"],
                )
                .execute()
            )

        raw: dict[str, Any] = await asyncio.to_thread(_call)

        headers: list[dict[str, str]] = (
            raw.get("payload", {}).get("headers", [])
        )

        result: dict[str, Any] = {
            "from_address": self._extract_header(headers, "From"),
            "to_addresses": self._split_addresses(
                self._extract_header(headers, "To")
            ),
            "cc_addresses": self._split_addresses(
                self._extract_header(headers, "Cc")
            ),
            "subject": self._extract_header(headers, "Subject"),
            "date": self._extract_header(headers, "Date"),
            "gmail_thread_id": raw.get("threadId", ""),
            "snippet": raw.get("snippet", ""),
        }

        logger.info(
            "gmail_client.message_fetched",
            user_email=user_email,
            message_id=message_id,
            subject=result["subject"],
        )
        return result

    @retry_with_backoff
    @circuit_breaker
    async def renew_watch(self, user_email: str) -> dict[str, Any]:
        """Renew the Gmail push-notification watch.

        Functionally identical to :meth:`setup_watch` -- the Gmail API
        treats a repeated ``watch()`` call as a renewal.
        """
        logger.info("gmail_client.renew_watch", user_email=user_email)

        body = self._build_watch_request(user_email)

        def _call() -> dict[str, Any]:
            return (
                self._service.users()
                .watch(userId=user_email, body=body)
                .execute()
            )

        response: dict[str, Any] = await asyncio.to_thread(_call)

        logger.info(
            "gmail_client.watch_renewed",
            user_email=user_email,
            history_id=response.get("historyId"),
            expiration=response.get("expiration"),
        )
        return response
