"""Seed script - Create default prompt version and sample pipeline config."""

import asyncio
import json

from sqlalchemy import select

from app.dependencies import get_session_factory
from app.models.pipeline_config import PipelineConfig
from app.models.prompt_version import PromptVersion

DEFAULT_INTENT_CATEGORIES = [
    "discovery_call_scheduled",
    "demo_scheduled",
    "demo_completed",
    "proposal_requested",
    "proposal_sent",
    "negotiation_active",
    "verbal_commitment",
    "contract_sent",
    "closed_won",
    "closed_lost",
    "objection_raised",
    "deal_stalled",
    "no_deal_signal",
]

DEFAULT_SYSTEM_PROMPT = """You are a sales deal progression analyst. Your task is to analyze sales email content and classify the deal progression intent.

You must respond with a JSON object containing:
- intent: One of the provided intent categories
- confidence_score: A number between 0.0 and 1.0 indicating your confidence
- reasoning: A brief explanation of why you chose this classification
- key_phrases: A list of key phrases from the email that support your classification
- direction: One of "forward" (deal progressing), "backward" (deal regressing), or "neutral" (no change)

Be precise and conservative. If you are not confident, use a lower confidence score.
Only classify as backward-moving intents (objection_raised, deal_stalled, closed_lost) when there is clear evidence of regression."""

DEFAULT_PROMPT_TEMPLATE = """Analyze the following sales email for deal progression signals.

Current deal context:
- Deal name: {deal_name}
- Current stage: {current_stage}

Email:
{email_content}

Valid intent categories: {intent_categories}

Respond with a JSON object containing: intent, confidence_score, reasoning, key_phrases, direction."""


async def seed() -> None:
    """Seed the database with default configuration."""
    session_factory = get_session_factory()

    async with session_factory() as db:
        # Check if prompt version already exists
        result = await db.execute(
            select(PromptVersion).where(PromptVersion.version == "1.0.0")
        )
        if not result.scalar_one_or_none():
            prompt = PromptVersion(
                version="1.0.0",
                prompt_template=DEFAULT_PROMPT_TEMPLATE,
                system_prompt=DEFAULT_SYSTEM_PROMPT,
                intent_categories=DEFAULT_INTENT_CATEGORIES,
                is_active=True,
                notes="Initial default prompt version",
            )
            db.add(prompt)
            print("Created default prompt version 1.0.0")
        else:
            print("Prompt version 1.0.0 already exists")

        # Check if sample pipeline config exists
        result = await db.execute(
            select(PipelineConfig).where(
                PipelineConfig.hubspot_pipeline_id == "default"
            )
        )
        if not result.scalar_one_or_none():
            stages = [
                {"id": "qualifiedtobuy", "name": "Qualified to Buy", "order": 1},
                {"id": "presentationscheduled", "name": "Presentation Scheduled", "order": 2},
                {"id": "decisionmakerboughtin", "name": "Decision Maker Bought-In", "order": 3},
                {"id": "contractsent", "name": "Contract Sent", "order": 4},
                {"id": "closedwon", "name": "Closed Won", "order": 5},
                {"id": "closedlost", "name": "Closed Lost", "order": 6},
            ]
            intent_rules = {
                "discovery_call_scheduled": "qualifiedtobuy",
                "demo_scheduled": "presentationscheduled",
                "demo_completed": "presentationscheduled",
                "proposal_requested": "decisionmakerboughtin",
                "proposal_sent": "decisionmakerboughtin",
                "negotiation_active": "decisionmakerboughtin",
                "verbal_commitment": "contractsent",
                "contract_sent": "contractsent",
                "closed_won": "closedwon",
                "closed_lost": "closedlost",
            }
            pipeline = PipelineConfig(
                hubspot_pipeline_id="default",
                pipeline_name="Sales Pipeline (Default)",
                stages=stages,
                intent_to_stage_rules=intent_rules,
                stage_ordering=stages,
                is_active=True,
            )
            db.add(pipeline)
            print("Created default pipeline config")
        else:
            print("Default pipeline config already exists")

        await db.commit()
        print("Seed completed successfully")


if __name__ == "__main__":
    asyncio.run(seed())
