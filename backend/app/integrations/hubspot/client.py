"""HubSpot CRM client implementing CRMProvider protocol.

Uses the official ``hubspot`` Python SDK (v3) with circuit breaker,
rate limiter, retry, and async wrappers.
"""

from __future__ import annotations

import asyncio
from typing import Any

import structlog
from hubspot import HubSpot
from hubspot.crm.deals import (
    PublicObjectSearchRequest,
    SimplePublicObjectInput,
)
from hubspot.crm.contacts import PublicObjectSearchRequest as ContactSearchRequest

from app.integrations.hubspot.protocol import CRMProvider
from app.utils.circuit_breaker import CircuitBreaker
from app.utils.rate_limiter import RateLimiter
from app.utils.retry import retry_with_backoff

logger = structlog.get_logger(__name__)

circuit_breaker = CircuitBreaker(
    name="hubspot",
    failure_threshold=5,
    reset_timeout=60,
)

# Properties we always request when fetching a deal.
_DEAL_PROPERTIES: list[str] = [
    "dealname",
    "pipeline",
    "dealstage",
    "amount",
    "closedate",
    "hubspot_owner_id",
]


def _deal_to_dict(deal: Any) -> dict[str, Any]:
    """Normalise a HubSpot deal object into a plain dict."""
    props = deal.properties or {}
    return {
        "id": deal.id,
        "deal_name": props.get("dealname"),
        "pipeline": props.get("pipeline"),
        "dealstage": props.get("dealstage"),
        "amount": props.get("amount"),
        "closedate": props.get("closedate"),
        "hubspot_owner_id": props.get("hubspot_owner_id"),
    }


class HubSpotClient(CRMProvider):
    """HubSpot CRM v3 client with circuit breaker, rate limiter, and retry.

    All public methods are async and use ``asyncio.to_thread`` to delegate
    synchronous HubSpot SDK calls so they never block the event loop.

    The *rate_limiter* is accepted as a constructor parameter to support
    dependency injection in tests.
    """

    def __init__(self, access_token: str, rate_limiter: RateLimiter) -> None:
        self._access_token = access_token
        self._rate_limiter = rate_limiter
        self._client = HubSpot(access_token=access_token)
        logger.info("hubspot_client.initialized")

    # ------------------------------------------------------------------
    # CRMProvider interface
    # ------------------------------------------------------------------

    @retry_with_backoff
    @circuit_breaker
    async def get_deal(self, deal_id: str) -> dict[str, Any]:
        """Get a single deal by its HubSpot ID."""
        logger.info("hubspot_client.get_deal", deal_id=deal_id)
        await self._rate_limiter.acquire()

        def _call() -> Any:
            return self._client.crm.deals.basic_api.get_by_id(
                deal_id=deal_id,
                properties=_DEAL_PROPERTIES,
            )

        deal = await asyncio.to_thread(_call)
        result = _deal_to_dict(deal)

        logger.info(
            "hubspot_client.deal_fetched",
            deal_id=deal_id,
            deal_name=result.get("deal_name"),
        )
        return result

    @retry_with_backoff
    @circuit_breaker
    async def search_deals_by_contact(
        self, contact_id: str
    ) -> list[dict[str, Any]]:
        """Find deals associated with a given contact via the associations API."""
        logger.info(
            "hubspot_client.search_deals_by_contact", contact_id=contact_id
        )
        await self._rate_limiter.acquire()

        def _call() -> Any:
            return (
                self._client.crm.contacts.associations_api
                .get_all(
                    contact_id=contact_id,
                    to_object_type="deals",
                )
            )

        associations = await asyncio.to_thread(_call)

        deal_ids: list[str] = [
            assoc.id for assoc in (associations.results or [])
        ]

        deals: list[dict[str, Any]] = []
        for did in deal_ids:
            deal = await self.get_deal(did)
            deals.append(deal)

        logger.info(
            "hubspot_client.deals_by_contact_fetched",
            contact_id=contact_id,
            deal_count=len(deals),
        )
        return deals

    @retry_with_backoff
    @circuit_breaker
    async def search_contacts_by_email(
        self, email: str
    ) -> list[dict[str, Any]]:
        """Search for contacts matching the given email address."""
        logger.info("hubspot_client.search_contacts_by_email", email=email)
        await self._rate_limiter.acquire()

        search_request = ContactSearchRequest(
            filter_groups=[
                {
                    "filters": [
                        {
                            "propertyName": "email",
                            "operator": "EQ",
                            "value": email,
                        }
                    ]
                }
            ],
            properties=["email", "firstname", "lastname", "company"],
        )

        def _call() -> Any:
            return self._client.crm.contacts.search_api.do_search(
                public_object_search_request=search_request,
            )

        response = await asyncio.to_thread(_call)

        contacts: list[dict[str, Any]] = []
        for contact in response.results or []:
            props = contact.properties or {}
            contacts.append(
                {
                    "id": contact.id,
                    "email": props.get("email"),
                    "firstname": props.get("firstname"),
                    "lastname": props.get("lastname"),
                    "company": props.get("company"),
                }
            )

        logger.info(
            "hubspot_client.contacts_found",
            email=email,
            count=len(contacts),
        )
        return contacts

    async def check_deal_stage(
        self, deal_id: str, expected_stage: str
    ) -> tuple[bool, str]:
        """Read-before-write conflict detection.

        Fetches the current deal from HubSpot and compares the live stage
        with *expected_stage*.

        Returns:
            (matches, live_stage) -- True if the live stage matches the
            expected stage, along with the actual live stage ID.
        """
        deal = await self.get_deal(deal_id)
        live_stage = deal.get("dealstage", "")
        matches = live_stage == expected_stage
        if not matches:
            logger.warn(
                "hubspot_client.stage_conflict",
                deal_id=deal_id,
                expected=expected_stage,
                live=live_stage,
            )
        return matches, live_stage

    @retry_with_backoff
    @circuit_breaker
    async def update_deal_stage(
        self, deal_id: str, stage_id: str, note: str
    ) -> dict[str, Any]:
        """Update a deal's stage and create an audit note engagement.

        Returns the updated deal dict.
        """
        logger.info(
            "hubspot_client.update_deal_stage",
            deal_id=deal_id,
            stage_id=stage_id,
        )
        await self._rate_limiter.acquire()

        # -- 1. Update the deal stage via PATCH -------------------------
        update_input = SimplePublicObjectInput(
            properties={"dealstage": stage_id},
        )

        def _update() -> Any:
            return self._client.crm.deals.basic_api.update(
                deal_id=deal_id,
                simple_public_object_input=update_input,
            )

        updated_deal = await asyncio.to_thread(_update)

        # -- 2. Create an audit note via the engagements API ------------
        await self._rate_limiter.acquire()

        note_body: dict[str, Any] = {
            "engagement": {
                "type": "NOTE",
                "active": True,
            },
            "associations": {
                "dealIds": [int(deal_id)],
            },
            "metadata": {
                "body": note,
            },
        }

        def _create_note() -> Any:
            return self._client.api_client.call_api(
                resource_path="/engagements/v1/engagements",
                method="POST",
                body=note_body,
                response_type="object",
            )

        await asyncio.to_thread(_create_note)

        result = _deal_to_dict(updated_deal)

        logger.info(
            "hubspot_client.deal_stage_updated",
            deal_id=deal_id,
            new_stage=stage_id,
        )
        return result

    @retry_with_backoff
    @circuit_breaker
    async def get_pipelines(self) -> list[dict[str, Any]]:
        """Get all deal pipelines with their stages."""
        logger.info("hubspot_client.get_pipelines")
        await self._rate_limiter.acquire()

        def _call() -> Any:
            return self._client.crm.pipelines.pipelines_api.get_all(
                object_type="deals",
            )

        response = await asyncio.to_thread(_call)

        pipelines: list[dict[str, Any]] = []
        for pipeline in response.results or []:
            stages = [
                {
                    "id": stage.id,
                    "label": stage.label,
                    "display_order": stage.display_order,
                    "metadata": stage.metadata,
                }
                for stage in (pipeline.stages or [])
            ]
            pipelines.append(
                {
                    "id": pipeline.id,
                    "label": pipeline.label,
                    "display_order": pipeline.display_order,
                    "stages": stages,
                }
            )

        logger.info(
            "hubspot_client.pipelines_fetched", count=len(pipelines)
        )
        return pipelines

    @retry_with_backoff
    @circuit_breaker
    async def get_owners(self) -> list[dict[str, Any]]:
        """Get all CRM owners."""
        logger.info("hubspot_client.get_owners")
        await self._rate_limiter.acquire()

        def _call() -> Any:
            return self._client.crm.owners.owners_api.get_page()

        response = await asyncio.to_thread(_call)

        owners: list[dict[str, Any]] = []
        for owner in response.results or []:
            owners.append(
                {
                    "id": owner.id,
                    "email": owner.email,
                    "first_name": owner.first_name,
                    "last_name": owner.last_name,
                    "user_id": owner.user_id,
                }
            )

        logger.info("hubspot_client.owners_fetched", count=len(owners))
        return owners
