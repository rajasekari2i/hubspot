"""MessagingProvider ABC - Interface for notification integrations."""

from abc import ABC, abstractmethod
from typing import Any


class MessagingProvider(ABC):
    """Abstract base class for messaging/notification integrations."""

    @abstractmethod
    async def send_recommendation(
        self,
        channel_or_user: str,
        recommendation_data: dict[str, Any],
    ) -> dict[str, Any]:
        """Send a recommendation notification with action buttons.

        Returns message metadata including timestamp for later updates.
        """
        ...

    @abstractmethod
    async def update_message(
        self,
        channel: str,
        message_ts: str,
        updated_blocks: list[dict[str, Any]],
    ) -> dict[str, Any]:
        """Update an existing message (e.g., after approval/rejection)."""
        ...

    @abstractmethod
    async def send_alert(self, channel: str, text: str) -> dict[str, Any]:
        """Send a plain text alert to a channel."""
        ...

    @abstractmethod
    async def health_check(self) -> bool:
        """Check if the messaging provider is reachable."""
        ...
