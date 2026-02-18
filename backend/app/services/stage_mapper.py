"""Stage mapper service - Intent to stage mapping with direction validation."""

import structlog

from app.models.intent_classification import Direction, IntentClassification
from app.models.pipeline_config import PipelineConfig

logger = structlog.get_logger()

# Intents that indicate regression (backward movement is valid)
REGRESSION_INTENTS = {"objection_raised", "deal_stalled", "closed_lost"}


class StageMapping:
    """Result of a stage mapping operation."""

    def __init__(
        self,
        *,
        target_stage_id: str,
        target_stage_name: str,
        is_valid: bool,
        reason: str = "",
    ):
        self.target_stage_id = target_stage_id
        self.target_stage_name = target_stage_name
        self.is_valid = is_valid
        self.reason = reason


def map_intent_to_stage(
    classification: IntentClassification,
    pipeline_config: PipelineConfig,
    current_stage_id: str,
) -> StageMapping | None:
    """Map a classified intent to a target CRM stage.

    Applies:
        1. Intent-to-stage lookup from pipeline config rules
        2. Direction validation (backward only for regression intents)
        3. Stage ordering enforcement

    Returns:
        StageMapping if a valid mapping exists, None if intent has no stage mapping.
    """
    intent = classification.intent
    rules = pipeline_config.intent_to_stage_rules or {}

    # Look up target stage for this intent
    target_stage_id = rules.get(intent)
    if not target_stage_id:
        logger.info("no_stage_mapping", intent=intent)
        return None

    # Get stage ordering and names
    stage_ordering = pipeline_config.stage_ordering or []
    stages_by_id = {s["id"]: s for s in (pipeline_config.stages or []) if isinstance(s, dict)}

    target_stage_info = stages_by_id.get(target_stage_id, {})
    target_stage_name = target_stage_info.get("name", target_stage_id)

    # If target is same as current, no change needed
    if target_stage_id == current_stage_id:
        return StageMapping(
            target_stage_id=target_stage_id,
            target_stage_name=target_stage_name,
            is_valid=False,
            reason="Target stage is same as current stage",
        )

    # Determine position in stage ordering
    stage_ids = [s["id"] if isinstance(s, dict) else s for s in stage_ordering]
    try:
        current_idx = stage_ids.index(current_stage_id)
        target_idx = stage_ids.index(target_stage_id)
    except ValueError:
        # Stage not found in ordering - allow the mapping but flag
        logger.warning(
            "stage_not_in_ordering",
            current_stage=current_stage_id,
            target_stage=target_stage_id,
        )
        return StageMapping(
            target_stage_id=target_stage_id,
            target_stage_name=target_stage_name,
            is_valid=True,
            reason="Stage ordering unknown",
        )

    is_backward = target_idx < current_idx
    direction = classification.direction

    # Enforce direction rules
    if is_backward and direction != Direction.BACKWARD:
        # Backward movement only allowed for regression intents
        if intent not in REGRESSION_INTENTS:
            return StageMapping(
                target_stage_id=target_stage_id,
                target_stage_name=target_stage_name,
                is_valid=False,
                reason=f"Backward stage movement not allowed for intent '{intent}'",
            )

    return StageMapping(
        target_stage_id=target_stage_id,
        target_stage_name=target_stage_name,
        is_valid=True,
        reason="forward" if not is_backward else "backward_regression",
    )
