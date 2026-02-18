"""CRMProvider ABC - Interface for CRM integrations."""

from abc import ABC, abstractmethod
from typing import Any


class CRMProvider(ABC):
    """Abstract base class for CRM provider integrations."""

    @abstractmethod
    async def get_deal(self, deal_id: str) -> dict[str, Any]:
        """Get a deal by its CRM ID."""
        ...

    @abstractmethod
    async def search_deals_by_contact(self, contact_id: str) -> list[dict[str, Any]]:
        """Search for deals associated with a contact."""
        ...

    @abstractmethod
    async def search_contacts_by_email(self, email: str) -> list[dict[str, Any]]:
        """Search for CRM contacts by email address."""
        ...

    @abstractmethod
    async def update_deal_stage(
        self, deal_id: str, stage_id: str, note: str
    ) -> dict[str, Any]:
        """Update a deal's stage and add an audit note."""
        ...

    @abstractmethod
    async def get_pipelines(self) -> list[dict[str, Any]]:
        """Get all CRM pipelines with stages."""
        ...

    @abstractmethod
    async def get_owners(self) -> list[dict[str, Any]]:
        """Get all CRM deal owners."""
        ...
