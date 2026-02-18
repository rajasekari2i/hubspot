"""Thread linker service - Email -> Contact -> Deal resolution with Redis cache."""

import json
import uuid
from decimal import Decimal

import structlog
import redis.asyncio as aioredis
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.integrations.hubspot.protocol import CRMProvider
from app.models.audit_log import ActorType
from app.models.deal import Deal
from app.models.email_message import EmailMessage
from app.models.email_thread import EmailThread
from app.services.audit import write_audit_log

logger = structlog.get_logger()

CACHE_TTL = 3600  # 1 hour


async def link_thread_to_deal(
    db: AsyncSession,
    redis_client: aioredis.Redis,
    hubspot_client: CRMProvider,
    email_msg: EmailMessage,
    trace_id: uuid.UUID,
) -> EmailThread | None:
    """Link an email to an existing thread and resolve the associated deal.

    Resolution chain: email participants -> CRM contacts -> associated deals.
    Uses Redis cache with 1h TTL for contact-to-deal resolution.

    Returns:
        The EmailThread with linked deal, or None if no deal could be resolved.
    """
    gmail_thread_id = email_msg.gmail_thread_id

    # Check for existing thread
    result = await db.execute(
        select(EmailThread).where(EmailThread.gmail_thread_id == gmail_thread_id)
    )
    thread = result.scalar_one_or_none()

    if thread:
        # Thread already linked - update message count
        thread.message_count += 1
        thread.last_activity_at = email_msg.received_at
        if thread.subject is None:
            thread.subject = email_msg.subject
        await db.flush()
        return thread

    # New thread - resolve contact -> deal
    all_addresses = [email_msg.from_address] + email_msg.to_addresses
    resolved_deals: list[dict] = []

    for addr in all_addresses:
        deals = await _resolve_email_to_deals(redis_client, hubspot_client, addr)
        resolved_deals.extend(deals)

    if not resolved_deals:
        await logger.ainfo("no_deals_found", gmail_thread_id=gmail_thread_id)
        # Create unlinked thread
        thread = EmailThread(
            gmail_thread_id=gmail_thread_id,
            subject=email_msg.subject,
            message_count=1,
            last_activity_at=email_msg.received_at,
            link_method="none",
        )
        db.add(thread)
        await db.flush()
        return thread

    # Pick the best deal match
    deal_match = _pick_best_deal(resolved_deals, email_msg.subject)

    if deal_match is None:
        await logger.awarn(
            "ambiguous_deal_match",
            gmail_thread_id=gmail_thread_id,
            candidate_count=len(resolved_deals),
        )
        thread = EmailThread(
            gmail_thread_id=gmail_thread_id,
            subject=email_msg.subject,
            message_count=1,
            last_activity_at=email_msg.received_at,
            link_method="ambiguous",
        )
        db.add(thread)
        await db.flush()
        return thread

    # Look up or create our cached Deal record
    deal = await _ensure_deal_cached(db, deal_match)

    thread = EmailThread(
        gmail_thread_id=gmail_thread_id,
        deal_id=deal.id if deal else None,
        subject=email_msg.subject,
        message_count=1,
        last_activity_at=email_msg.received_at,
        link_confidence=Decimal(str(deal_match.get("confidence", 0.8))),
        link_method=deal_match.get("method", "email_match"),
    )
    db.add(thread)
    await db.flush()

    # Audit log
    await write_audit_log(
        db,
        action="thread_linked",
        entity_type="email_thread",
        entity_id=thread.id,
        actor_type=ActorType.SYSTEM,
        trace_id=trace_id,
        after_state={
            "gmail_thread_id": gmail_thread_id,
            "deal_id": str(deal.id) if deal else None,
            "link_method": thread.link_method,
        },
    )

    return thread


async def _resolve_email_to_deals(
    redis_client: aioredis.Redis,
    hubspot_client: CRMProvider,
    email_address: str,
) -> list[dict]:
    """Resolve an email address to associated CRM deals, with Redis caching."""
    cache_key = f"contact_deals:{email_address}"

    # Check cache
    cached = await redis_client.get(cache_key)
    if cached:
        return json.loads(cached)

    # Look up contact by email
    contacts = await hubspot_client.search_contacts_by_email(email_address)
    if not contacts:
        await redis_client.setex(cache_key, CACHE_TTL, "[]")
        return []

    # For each contact, find associated deals
    all_deals: list[dict] = []
    for contact in contacts:
        contact_id = contact.get("id", "")
        deals = await hubspot_client.search_deals_by_contact(contact_id)
        for deal in deals:
            deal["method"] = "email_match"
            deal["confidence"] = 0.9
        all_deals.extend(deals)

    # Cache the result
    await redis_client.setex(cache_key, CACHE_TTL, json.dumps(all_deals, default=str))
    return all_deals


def _pick_best_deal(deals: list[dict], email_subject: str) -> dict | None:
    """Pick the most likely deal from candidates using subject fuzzy matching and recency.

    If only one deal, return it directly. If multiple, try subject matching.
    If still ambiguous, return None to flag for manual disambiguation.
    """
    if len(deals) == 1:
        return deals[0]

    # Deduplicate by deal ID
    seen_ids: set[str] = set()
    unique_deals: list[dict] = []
    for d in deals:
        did = d.get("id", "")
        if did not in seen_ids:
            seen_ids.add(did)
            unique_deals.append(d)

    if len(unique_deals) == 1:
        return unique_deals[0]

    # Try subject line matching
    subject_lower = email_subject.lower() if email_subject else ""
    scored_deals = []
    for deal in unique_deals:
        deal_name = deal.get("deal_name", "").lower()
        # Simple overlap scoring
        words = set(deal_name.split())
        subject_words = set(subject_lower.split())
        overlap = len(words & subject_words)
        scored_deals.append((overlap, deal))

    scored_deals.sort(key=lambda x: x[0], reverse=True)

    if scored_deals and scored_deals[0][0] > 0:
        # If top match has significantly more overlap than second
        if len(scored_deals) == 1 or scored_deals[0][0] > scored_deals[1][0]:
            best = scored_deals[0][1]
            best["method"] = "subject_fuzzy"
            best["confidence"] = 0.7
            return best

    # Ambiguous - flag for manual resolution
    return None


async def _ensure_deal_cached(db: AsyncSession, deal_data: dict) -> Deal | None:
    """Ensure we have a cached Deal record for the HubSpot deal."""
    hubspot_deal_id = str(deal_data.get("id", ""))
    if not hubspot_deal_id:
        return None

    result = await db.execute(
        select(Deal).where(Deal.hubspot_deal_id == hubspot_deal_id)
    )
    deal = result.scalar_one_or_none()

    # Deal should already exist from pipeline sync, but don't fail if not
    return deal
