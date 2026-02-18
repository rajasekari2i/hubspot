"""HubSpot pipeline metadata sync worker.

Periodically fetches pipeline/stage definitions from HubSpot and upserts
PipelineConfig records.  Detects stage changes (additions, removals,
reordering) and logs them via the audit service.
"""

import asyncio
from typing import Any

import structlog
from sqlalchemy import select

from app.config import get_settings
from app.dependencies import get_session_factory
from app.integrations.hubspot.client import HubSpotClient
from app.models.audit_log import ActorType
from app.models.pipeline_config import PipelineConfig
from app.services.audit import write_audit_log
from app.utils.rate_limiter import RateLimiter

logger = structlog.get_logger()


def _build_stages_list(raw_stages: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """Normalise HubSpot stage data into the JSONB format we persist."""
    stages = []
    for s in sorted(raw_stages, key=lambda x: x.get("display_order", 0)):
        stages.append({
            "id": s["id"],
            "name": s["label"],
            "order": s.get("display_order", 0),
        })
    return stages


def _build_stage_ordering(stages: list[dict[str, Any]]) -> list[str]:
    """Return ordered stage IDs for direction validation."""
    return [s["id"] for s in stages]


def _detect_changes(
    existing: PipelineConfig, new_stages: list[dict[str, Any]]
) -> dict[str, Any] | None:
    """Compare existing stages with freshly fetched stages.

    Returns a dict describing the changes, or ``None`` if nothing changed.
    """
    old_stages = existing.stages if isinstance(existing.stages, list) else []
    old_ids = {s["id"] for s in old_stages}
    new_ids = {s["id"] for s in new_stages}

    added = new_ids - old_ids
    removed = old_ids - new_ids
    old_order = [s["id"] for s in old_stages]
    new_order = [s["id"] for s in new_stages]

    if not added and not removed and old_order == new_order:
        return None

    return {
        "added_stages": sorted(added),
        "removed_stages": sorted(removed),
        "reordered": old_order != new_order,
    }


async def sync_pipelines() -> None:
    """Fetch all HubSpot pipelines and upsert local PipelineConfig records."""
    settings = get_settings()
    session_factory = get_session_factory()

    if not settings.hubspot_access_token:
        await logger.awarning("pipeline_sync.skipped", reason="no HubSpot token configured")
        return

    rate_limiter = RateLimiter(
        redis_url=settings.redis_url,
        key_prefix="hubspot",
        max_requests=110,
        window_seconds=10,
    )
    hubspot_client = HubSpotClient(
        access_token=settings.hubspot_access_token,
        rate_limiter=rate_limiter,
    )

    try:
        pipelines = await hubspot_client.get_pipelines()
    except Exception as exc:
        await logger.aerror("pipeline_sync.fetch_failed", error=str(exc))
        # Alert ops via Slack
        try:
            from app.integrations.slack.client import SlackClient

            slack = SlackClient(
                bot_token=settings.slack_bot_token,
                signing_secret=settings.slack_signing_secret,
            )
            await slack.send_alert(
                channel=settings.slack_alert_channel,
                text=f"Pipeline sync failed: {exc}",
            )
        except Exception:
            pass
        return

    async with session_factory() as db:
        upserted = 0
        changed = 0

        for pipeline_data in pipelines:
            hubspot_id = pipeline_data["id"]
            label = pipeline_data["label"]
            stages = _build_stages_list(pipeline_data.get("stages", []))
            stage_ordering = _build_stage_ordering(stages)

            result = await db.execute(
                select(PipelineConfig).where(
                    PipelineConfig.hubspot_pipeline_id == hubspot_id
                )
            )
            existing = result.scalar_one_or_none()

            if existing:
                changes = _detect_changes(existing, stages)
                before_state = {
                    "pipeline_name": existing.pipeline_name,
                    "stages": existing.stages,
                }

                existing.pipeline_name = label
                existing.stages = stages
                existing.stage_ordering = stage_ordering

                if changes:
                    changed += 1
                    await db.flush()
                    await write_audit_log(
                        db,
                        action="config_changed",
                        entity_type="pipeline_config",
                        entity_id=existing.id,
                        actor_type=ActorType.SYSTEM,
                        actor_id="pipeline_sync",
                        before_state=before_state,
                        after_state={
                            "pipeline_name": label,
                            "stages": stages,
                            "changes": changes,
                        },
                    )
                    await logger.ainfo(
                        "pipeline_sync.stages_changed",
                        hubspot_pipeline_id=hubspot_id,
                        changes=changes,
                    )
            else:
                # Create new PipelineConfig with default thresholds
                new_config = PipelineConfig(
                    hubspot_pipeline_id=hubspot_id,
                    pipeline_name=label,
                    stages=stages,
                    intent_to_stage_rules={},
                    stage_ordering=stage_ordering,
                )
                db.add(new_config)
                await db.flush()
                await write_audit_log(
                    db,
                    action="config_changed",
                    entity_type="pipeline_config",
                    entity_id=new_config.id,
                    actor_type=ActorType.SYSTEM,
                    actor_id="pipeline_sync",
                    before_state=None,
                    after_state={
                        "pipeline_name": label,
                        "stages": stages,
                    },
                )
                await logger.ainfo(
                    "pipeline_sync.new_pipeline",
                    hubspot_pipeline_id=hubspot_id,
                    pipeline_name=label,
                )

            upserted += 1

        await db.commit()

        await logger.ainfo(
            "pipeline_sync.completed",
            pipelines_processed=upserted,
            stages_changed=changed,
        )


if __name__ == "__main__":
    asyncio.run(sync_pipelines())
