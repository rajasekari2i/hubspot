"""Admin routes - User management, pipeline config, and prompt version management."""

import uuid
from datetime import datetime, timezone

import structlog
from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel, Field
from sqlalchemy import select, update
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.middleware.auth import require_roles
from app.dependencies import get_db
from app.models.audit_log import ActorType
from app.models.pipeline_config import PipelineConfig
from app.models.prompt_version import PromptVersion
from app.models.user_config import UserConfig, UserRole
from app.services.audit import write_audit_log

logger = structlog.get_logger()

router = APIRouter(prefix="/admin", tags=["Admin"])


# ---------- Request / Response schemas ----------


class UserResponse(BaseModel):
    id: str
    email: str
    display_name: str
    role: str
    hubspot_owner_id: str | None = None
    slack_user_id: str | None = None
    is_active: bool
    created_at: str

    class Config:
        from_attributes = True


class CreateUserRequest(BaseModel):
    email: str
    display_name: str
    role: str = Field(..., pattern="^(admin|revops|sales_user)$")
    hubspot_owner_id: str | None = None
    slack_user_id: str | None = None


class UpdateUserRequest(BaseModel):
    display_name: str | None = None
    role: str | None = Field(None, pattern="^(admin|revops|sales_user)$")
    hubspot_owner_id: str | None = None
    slack_user_id: str | None = None
    is_active: bool | None = None


class PipelineConfigResponse(BaseModel):
    id: str
    hubspot_pipeline_id: str
    pipeline_name: str
    stages: list
    intent_to_stage_rules: dict
    is_active: bool
    recommendation_threshold: float
    logging_threshold: float
    approval_timeout_hours: int
    max_snoozes: int
    created_at: str
    updated_at: str

    class Config:
        from_attributes = True


class UpdatePipelineConfigRequest(BaseModel):
    intent_to_stage_rules: dict | None = None
    recommendation_threshold: float | None = Field(None, ge=0, le=1)
    logging_threshold: float | None = Field(None, ge=0, le=1)
    approval_timeout_hours: int | None = Field(None, ge=1)
    max_snoozes: int | None = Field(None, ge=0)
    is_active: bool | None = None


class PromptVersionResponse(BaseModel):
    id: str
    version: str
    prompt_template: str
    system_prompt: str
    intent_categories: list[str]
    is_active: bool
    notes: str | None = None
    created_at: str

    class Config:
        from_attributes = True


class CreatePromptVersionRequest(BaseModel):
    version: str
    prompt_template: str
    system_prompt: str
    intent_categories: list[str]
    notes: str | None = None


# ---------- User Management (T072) ----------


@router.get("/users", response_model=list[UserResponse])
async def list_users(
    db: AsyncSession = Depends(get_db),
    current_user: UserConfig = Depends(require_roles(UserRole.ADMIN)),
) -> list[UserResponse]:
    """List all system users. Admin only."""
    result = await db.execute(select(UserConfig).order_by(UserConfig.created_at.desc()))
    users = result.scalars().all()
    return [
        UserResponse(
            id=str(u.id),
            email=u.email,
            display_name=u.display_name,
            role=u.role.value,
            hubspot_owner_id=u.hubspot_owner_id,
            slack_user_id=u.slack_user_id,
            is_active=u.is_active,
            created_at=u.created_at.isoformat(),
        )
        for u in users
    ]


@router.post("/users", response_model=UserResponse, status_code=status.HTTP_201_CREATED)
async def create_user(
    body: CreateUserRequest,
    db: AsyncSession = Depends(get_db),
    current_user: UserConfig = Depends(require_roles(UserRole.ADMIN)),
) -> UserResponse:
    """Create a new user with role and external account linking."""
    # Check if email already exists
    existing = await db.execute(
        select(UserConfig).where(UserConfig.email == body.email)
    )
    if existing.scalar_one_or_none():
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=f"User with email '{body.email}' already exists",
        )

    user = UserConfig(
        email=body.email,
        display_name=body.display_name,
        role=UserRole(body.role),
        hubspot_owner_id=body.hubspot_owner_id,
        slack_user_id=body.slack_user_id,
        is_active=True,
    )
    db.add(user)
    await db.flush()

    await write_audit_log(
        db,
        action="user_created",
        entity_type="user_config",
        entity_id=user.id,
        actor_type=ActorType.USER,
        actor_id=str(current_user.id),
        after_state={"email": body.email, "role": body.role},
    )

    await logger.ainfo("user_created", email=body.email, actor=current_user.email)

    return UserResponse(
        id=str(user.id),
        email=user.email,
        display_name=user.display_name,
        role=user.role.value,
        hubspot_owner_id=user.hubspot_owner_id,
        slack_user_id=user.slack_user_id,
        is_active=user.is_active,
        created_at=user.created_at.isoformat(),
    )


@router.patch("/users/{user_id}", response_model=UserResponse)
async def update_user(
    user_id: uuid.UUID,
    body: UpdateUserRequest,
    db: AsyncSession = Depends(get_db),
    current_user: UserConfig = Depends(require_roles(UserRole.ADMIN)),
) -> UserResponse:
    """Update user details (role, external accounts, active status)."""
    result = await db.execute(select(UserConfig).where(UserConfig.id == user_id))
    user = result.scalar_one_or_none()
    if not user:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="User not found")

    before_state = {"role": user.role.value, "is_active": user.is_active}
    updates = body.model_dump(exclude_unset=True)

    if "role" in updates and updates["role"] is not None:
        user.role = UserRole(updates["role"])
    if "display_name" in updates and updates["display_name"] is not None:
        user.display_name = updates["display_name"]
    if "hubspot_owner_id" in updates:
        user.hubspot_owner_id = updates["hubspot_owner_id"]
    if "slack_user_id" in updates:
        user.slack_user_id = updates["slack_user_id"]
    if "is_active" in updates and updates["is_active"] is not None:
        user.is_active = updates["is_active"]

    await db.flush()

    await write_audit_log(
        db,
        action="user_updated",
        entity_type="user_config",
        entity_id=user.id,
        actor_type=ActorType.USER,
        actor_id=str(current_user.id),
        before_state=before_state,
        after_state=updates,
    )

    return UserResponse(
        id=str(user.id),
        email=user.email,
        display_name=user.display_name,
        role=user.role.value,
        hubspot_owner_id=user.hubspot_owner_id,
        slack_user_id=user.slack_user_id,
        is_active=user.is_active,
        created_at=user.created_at.isoformat(),
    )


@router.delete("/users/{user_id}", status_code=status.HTTP_204_NO_CONTENT)
async def deactivate_user(
    user_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    current_user: UserConfig = Depends(require_roles(UserRole.ADMIN)),
) -> None:
    """Soft-deactivate a user (set is_active=False)."""
    result = await db.execute(select(UserConfig).where(UserConfig.id == user_id))
    user = result.scalar_one_or_none()
    if not user:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="User not found")

    user.is_active = False
    await db.flush()

    await write_audit_log(
        db,
        action="user_deactivated",
        entity_type="user_config",
        entity_id=user.id,
        actor_type=ActorType.USER,
        actor_id=str(current_user.id),
        before_state={"is_active": True},
        after_state={"is_active": False},
    )

    await logger.ainfo("user_deactivated", email=user.email, actor=current_user.email)


# ---------- Pipeline Config (T073) ----------


@router.get("/pipelines", response_model=list[PipelineConfigResponse])
async def list_pipeline_configs(
    db: AsyncSession = Depends(get_db),
    current_user: UserConfig = Depends(require_roles(UserRole.ADMIN, UserRole.REVOPS)),
) -> list[PipelineConfigResponse]:
    """List all pipeline configurations."""
    result = await db.execute(select(PipelineConfig).order_by(PipelineConfig.pipeline_name))
    configs = result.scalars().all()
    return [
        PipelineConfigResponse(
            id=str(c.id),
            hubspot_pipeline_id=c.hubspot_pipeline_id,
            pipeline_name=c.pipeline_name,
            stages=c.stages if isinstance(c.stages, list) else [],
            intent_to_stage_rules=c.intent_to_stage_rules if isinstance(c.intent_to_stage_rules, dict) else {},
            is_active=c.is_active,
            recommendation_threshold=float(c.recommendation_threshold),
            logging_threshold=float(c.logging_threshold),
            approval_timeout_hours=c.approval_timeout_hours,
            max_snoozes=c.max_snoozes,
            created_at=c.created_at.isoformat(),
            updated_at=c.updated_at.isoformat(),
        )
        for c in configs
    ]


@router.get("/pipelines/{pipeline_id}", response_model=PipelineConfigResponse)
async def get_pipeline_config(
    pipeline_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    current_user: UserConfig = Depends(require_roles(UserRole.ADMIN, UserRole.REVOPS)),
) -> PipelineConfigResponse:
    """Get a single pipeline configuration."""
    result = await db.execute(select(PipelineConfig).where(PipelineConfig.id == pipeline_id))
    config = result.scalar_one_or_none()
    if not config:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Pipeline config not found")

    return PipelineConfigResponse(
        id=str(config.id),
        hubspot_pipeline_id=config.hubspot_pipeline_id,
        pipeline_name=config.pipeline_name,
        stages=config.stages if isinstance(config.stages, list) else [],
        intent_to_stage_rules=config.intent_to_stage_rules if isinstance(config.intent_to_stage_rules, dict) else {},
        is_active=config.is_active,
        recommendation_threshold=float(config.recommendation_threshold),
        logging_threshold=float(config.logging_threshold),
        approval_timeout_hours=config.approval_timeout_hours,
        max_snoozes=config.max_snoozes,
        created_at=config.created_at.isoformat(),
        updated_at=config.updated_at.isoformat(),
    )


@router.patch("/pipelines/{pipeline_id}", response_model=PipelineConfigResponse)
async def update_pipeline_config(
    pipeline_id: uuid.UUID,
    body: UpdatePipelineConfigRequest,
    db: AsyncSession = Depends(get_db),
    current_user: UserConfig = Depends(require_roles(UserRole.ADMIN, UserRole.REVOPS)),
) -> PipelineConfigResponse:
    """Update pipeline configuration (rules, thresholds, timeout, max_snoozes)."""
    result = await db.execute(select(PipelineConfig).where(PipelineConfig.id == pipeline_id))
    config = result.scalar_one_or_none()
    if not config:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Pipeline config not found")

    before_state = {
        "recommendation_threshold": float(config.recommendation_threshold),
        "logging_threshold": float(config.logging_threshold),
        "approval_timeout_hours": config.approval_timeout_hours,
        "max_snoozes": config.max_snoozes,
    }

    updates = body.model_dump(exclude_unset=True)

    if "intent_to_stage_rules" in updates and updates["intent_to_stage_rules"] is not None:
        config.intent_to_stage_rules = updates["intent_to_stage_rules"]
    if "recommendation_threshold" in updates and updates["recommendation_threshold"] is not None:
        config.recommendation_threshold = updates["recommendation_threshold"]
    if "logging_threshold" in updates and updates["logging_threshold"] is not None:
        config.logging_threshold = updates["logging_threshold"]
    if "approval_timeout_hours" in updates and updates["approval_timeout_hours"] is not None:
        config.approval_timeout_hours = updates["approval_timeout_hours"]
    if "max_snoozes" in updates and updates["max_snoozes"] is not None:
        config.max_snoozes = updates["max_snoozes"]
    if "is_active" in updates and updates["is_active"] is not None:
        config.is_active = updates["is_active"]

    await db.flush()

    await write_audit_log(
        db,
        action="pipeline_config_updated",
        entity_type="pipeline_config",
        entity_id=config.id,
        actor_type=ActorType.USER,
        actor_id=str(current_user.id),
        before_state=before_state,
        after_state=updates,
    )

    await logger.ainfo(
        "pipeline_config_updated",
        pipeline_id=str(config.id),
        actor=current_user.email,
    )

    return PipelineConfigResponse(
        id=str(config.id),
        hubspot_pipeline_id=config.hubspot_pipeline_id,
        pipeline_name=config.pipeline_name,
        stages=config.stages if isinstance(config.stages, list) else [],
        intent_to_stage_rules=config.intent_to_stage_rules if isinstance(config.intent_to_stage_rules, dict) else {},
        is_active=config.is_active,
        recommendation_threshold=float(config.recommendation_threshold),
        logging_threshold=float(config.logging_threshold),
        approval_timeout_hours=config.approval_timeout_hours,
        max_snoozes=config.max_snoozes,
        created_at=config.created_at.isoformat(),
        updated_at=config.updated_at.isoformat(),
    )


# ---------- Prompt Version Management (T074) ----------


@router.get("/prompts", response_model=list[PromptVersionResponse])
async def list_prompt_versions(
    db: AsyncSession = Depends(get_db),
    current_user: UserConfig = Depends(require_roles(UserRole.ADMIN, UserRole.REVOPS)),
) -> list[PromptVersionResponse]:
    """List all prompt versions."""
    result = await db.execute(
        select(PromptVersion).order_by(PromptVersion.created_at.desc())
    )
    versions = result.scalars().all()
    return [
        PromptVersionResponse(
            id=str(v.id),
            version=v.version,
            prompt_template=v.prompt_template,
            system_prompt=v.system_prompt,
            intent_categories=v.intent_categories if isinstance(v.intent_categories, list) else [],
            is_active=v.is_active,
            notes=v.notes,
            created_at=v.created_at.isoformat(),
        )
        for v in versions
    ]


@router.post("/prompts", response_model=PromptVersionResponse, status_code=status.HTTP_201_CREATED)
async def create_prompt_version(
    body: CreatePromptVersionRequest,
    db: AsyncSession = Depends(get_db),
    current_user: UserConfig = Depends(require_roles(UserRole.ADMIN)),
) -> PromptVersionResponse:
    """Create a new prompt version (inactive by default)."""
    # Check if version already exists
    existing = await db.execute(
        select(PromptVersion).where(PromptVersion.version == body.version)
    )
    if existing.scalar_one_or_none():
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=f"Prompt version '{body.version}' already exists",
        )

    version = PromptVersion(
        version=body.version,
        prompt_template=body.prompt_template,
        system_prompt=body.system_prompt,
        intent_categories=body.intent_categories,
        is_active=False,
        notes=body.notes,
    )
    db.add(version)
    await db.flush()

    await write_audit_log(
        db,
        action="prompt_version_created",
        entity_type="prompt_version",
        entity_id=version.id,
        actor_type=ActorType.USER,
        actor_id=str(current_user.id),
        after_state={"version": body.version},
    )

    await logger.ainfo("prompt_version_created", version=body.version, actor=current_user.email)

    return PromptVersionResponse(
        id=str(version.id),
        version=version.version,
        prompt_template=version.prompt_template,
        system_prompt=version.system_prompt,
        intent_categories=version.intent_categories,
        is_active=version.is_active,
        notes=version.notes,
        created_at=version.created_at.isoformat(),
    )


@router.post("/prompts/{prompt_id}/activate", response_model=PromptVersionResponse)
async def activate_prompt_version(
    prompt_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    current_user: UserConfig = Depends(require_roles(UserRole.ADMIN)),
) -> PromptVersionResponse:
    """Activate a prompt version (auto-deactivates the current active version)."""
    result = await db.execute(select(PromptVersion).where(PromptVersion.id == prompt_id))
    version = result.scalar_one_or_none()
    if not version:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Prompt version not found")

    # Deactivate all other versions
    await db.execute(
        update(PromptVersion)
        .where(PromptVersion.is_active.is_(True))
        .values(is_active=False)
    )

    version.is_active = True
    await db.flush()

    await write_audit_log(
        db,
        action="prompt_version_activated",
        entity_type="prompt_version",
        entity_id=version.id,
        actor_type=ActorType.USER,
        actor_id=str(current_user.id),
        after_state={"version": version.version, "is_active": True},
    )

    await logger.ainfo(
        "prompt_version_activated",
        version=version.version,
        actor=current_user.email,
    )

    return PromptVersionResponse(
        id=str(version.id),
        version=version.version,
        prompt_template=version.prompt_template,
        system_prompt=version.system_prompt,
        intent_categories=version.intent_categories,
        is_active=version.is_active,
        notes=version.notes,
        created_at=version.created_at.isoformat(),
    )


@router.post("/prompts/{prompt_id}/rollback", response_model=PromptVersionResponse)
async def rollback_prompt_version(
    prompt_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    current_user: UserConfig = Depends(require_roles(UserRole.ADMIN)),
) -> PromptVersionResponse:
    """Rollback to a previous prompt version (alias for activate)."""
    return await activate_prompt_version(prompt_id, db, current_user)
