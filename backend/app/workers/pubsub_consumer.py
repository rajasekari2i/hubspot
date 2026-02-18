"""Pub/Sub pull consumer worker - Email processing pipeline orchestration."""

import asyncio
import json
import uuid

import structlog

from app.config import get_settings
from app.dependencies import get_db, get_redis, get_session_factory
from app.models.email_message import EmailMessage
from app.models.email_thread import EmailThread
from app.models.prompt_version import PromptVersion
from app.models.pipeline_config import PipelineConfig
from app.models.user_config import UserConfig
from app.models.deal import Deal
from app.services.ingestion import ingest_new_emails
from app.services.thread_linker import link_thread_to_deal
from app.services.intent_analyzer import classify_email_intent
from app.services.stage_mapper import map_intent_to_stage
from app.services.recommendation import generate_recommendation
from app.services.notification import send_recommendation_notification

logger = structlog.get_logger()


async def process_gmail_notification(
    user_email: str,
    history_id: int,
) -> None:
    """Process a single Gmail push notification.

    Pipeline: ingest -> link thread -> classify intent -> map stage ->
              generate recommendation -> notify via Slack.
    """
    trace_id = uuid.uuid4()
    structlog.contextvars.bind_contextvars(trace_id=str(trace_id))

    settings = get_settings()
    session_factory = get_session_factory()
    redis_client = await get_redis()

    async with session_factory() as db:
        try:
            # Look up user
            from sqlalchemy import select

            result = await db.execute(
                select(UserConfig).where(
                    UserConfig.email == user_email,
                    UserConfig.is_active.is_(True),
                )
            )
            user = result.scalar_one_or_none()
            if not user:
                await logger.awarn("unknown_user", email=user_email)
                return

            last_history_id = user.gmail_last_history_id or history_id

            # Initialize integration clients (lazy import to avoid circular)
            from app.integrations.gmail.client import GmailClient
            from app.integrations.hubspot.client import HubSpotClient
            from app.integrations.slack.client import SlackClient

            gmail_client = GmailClient(
                credentials={},  # Will use service account or stored credentials
                project_id=settings.google_cloud_project,
            )
            hubspot_client = HubSpotClient(access_token=settings.hubspot_access_token)
            slack_client = SlackClient(
                bot_token=settings.slack_bot_token,
                signing_secret=settings.slack_signing_secret,
            )

            # Step 1: Ingest new emails
            new_messages = await ingest_new_emails(
                db, gmail_client, user_email, user.id, last_history_id, trace_id
            )

            if not new_messages:
                return

            # Update user's last history ID
            user.gmail_last_history_id = history_id

            # Get active prompt version
            prompt_result = await db.execute(
                select(PromptVersion).where(PromptVersion.is_active.is_(True))
            )
            active_prompt = prompt_result.scalar_one_or_none()
            if not active_prompt:
                await logger.aerror("no_active_prompt")
                return

            # Initialize LLM provider
            from app.integrations.llm.anthropic import AnthropicClient

            llm_provider = AnthropicClient(
                api_key=settings.anthropic_api_key,
                model=settings.llm_primary_model,
            )

            # Process each new message through the pipeline
            for email_msg in new_messages:
                await _process_single_email(
                    db=db,
                    redis_client=redis_client,
                    gmail_client=gmail_client,
                    hubspot_client=hubspot_client,
                    slack_client=slack_client,
                    llm_provider=llm_provider,
                    email_msg=email_msg,
                    user=user,
                    active_prompt=active_prompt,
                    trace_id=trace_id,
                )

            await db.commit()

        except Exception as exc:
            await db.rollback()
            await logger.aerror("pipeline_error", error=str(exc))
            raise


async def _process_single_email(
    db,
    redis_client,
    gmail_client,
    hubspot_client,
    slack_client,
    llm_provider,
    email_msg: EmailMessage,
    user: UserConfig,
    active_prompt: PromptVersion,
    trace_id: uuid.UUID,
) -> None:
    """Process a single email through the full pipeline."""
    from sqlalchemy import select

    # Step 2: Link thread to deal
    thread = await link_thread_to_deal(
        db, redis_client, hubspot_client, email_msg, trace_id
    )
    if not thread or not thread.deal_id:
        await logger.ainfo("no_deal_linked", gmail_thread_id=email_msg.gmail_thread_id)
        return

    # Get deal
    deal_result = await db.execute(select(Deal).where(Deal.id == thread.deal_id))
    deal = deal_result.scalar_one_or_none()
    if not deal:
        return

    # Get pipeline config
    pipeline_result = await db.execute(
        select(PipelineConfig).where(
            PipelineConfig.hubspot_pipeline_id == deal.hubspot_pipeline_id,
            PipelineConfig.is_active.is_(True),
        )
    )
    pipeline_config = pipeline_result.scalar_one_or_none()
    if not pipeline_config:
        await logger.awarn("no_pipeline_config", pipeline_id=deal.hubspot_pipeline_id)
        return

    # Step 3: Classify intent
    deal_context = {
        "deal_id": deal.id,
        "deal_name": deal.deal_name,
        "current_stage": deal.current_stage,
        "current_stage_name": deal.current_stage_name,
        "thread_summary": "",  # Could aggregate thread messages
    }

    classification = await classify_email_intent(
        db, llm_provider, email_msg, deal_context, active_prompt, trace_id
    )

    # Step 4: Map intent to stage
    stage_mapping = map_intent_to_stage(
        classification, pipeline_config, deal.current_stage
    )
    if not stage_mapping:
        return

    # Step 5: Generate recommendation
    recommendation = await generate_recommendation(
        db,
        email_msg=email_msg,
        thread=thread,
        deal=deal,
        classification=classification,
        stage_mapping=stage_mapping,
        pipeline_config=pipeline_config,
        trace_id=trace_id,
    )

    if not recommendation:
        return

    # Step 6: Send notification
    await send_recommendation_notification(
        db, slack_client, recommendation, deal, user
    )


async def run_consumer() -> None:
    """Main consumer loop - Pull messages from Pub/Sub subscription."""
    from google.cloud import pubsub_v1

    settings = get_settings()
    subscriber = pubsub_v1.SubscriberClient()
    subscription_path = subscriber.subscription_path(
        settings.google_cloud_project, settings.pubsub_subscription
    )

    await logger.ainfo("consumer_starting", subscription=subscription_path)

    while True:
        try:
            # Pull messages (synchronous SDK, run in thread)
            response = await asyncio.to_thread(
                subscriber.pull,
                request={"subscription": subscription_path, "max_messages": 10},
                timeout=30,
            )

            if not response.received_messages:
                await asyncio.sleep(1)
                continue

            ack_ids = []
            for msg in response.received_messages:
                try:
                    data = json.loads(msg.message.data.decode("utf-8"))
                    user_email = data.get("emailAddress", "")
                    history_id = data.get("historyId", 0)

                    await process_gmail_notification(user_email, history_id)
                    ack_ids.append(msg.ack_id)

                except Exception as exc:
                    await logger.aerror(
                        "message_processing_error",
                        message_id=msg.message.message_id,
                        error=str(exc),
                    )
                    # Don't ack - Pub/Sub will redeliver
                    # TODO: Route to DLQ after max retries

            # Acknowledge processed messages
            if ack_ids:
                await asyncio.to_thread(
                    subscriber.acknowledge,
                    request={"subscription": subscription_path, "ack_ids": ack_ids},
                )

        except Exception as exc:
            await logger.aerror("consumer_error", error=str(exc))
            await asyncio.sleep(5)


if __name__ == "__main__":
    asyncio.run(run_consumer())
