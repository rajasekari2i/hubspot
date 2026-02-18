"""EmailProvider ABC - Interface for email monitoring integrations."""

from abc import ABC, abstractmethod
from typing import Any


class EmailProvider(ABC):
    """Abstract base class for email provider integrations."""

    @abstractmethod
    async def setup_watch(self, user_email: str) -> dict[str, Any]:
        """Setup push notification watch for a user's mailbox.

        Returns watch metadata including expiration.
        """
        ...

    @abstractmethod
    async def get_history(
        self, user_email: str, start_history_id: int
    ) -> list[dict[str, Any]]:
        """Get mailbox changes since the given history ID.

        Returns list of history records with added message IDs.
        """
        ...

    @abstractmethod
    async def get_message(
        self, user_email: str, message_id: str
    ) -> dict[str, Any]:
        """Get message metadata and snippet by ID.

        Returns parsed message with headers, snippet, and thread ID.
        """
        ...

    @abstractmethod
    async def renew_watch(self, user_email: str) -> dict[str, Any]:
        """Renew an existing watch before expiration."""
        ...
