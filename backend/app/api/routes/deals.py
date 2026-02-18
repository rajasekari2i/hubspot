"""Deal routes - List and detail endpoints for monitored deals."""

import uuid

import structlog
from fastapi import APIRouter, Depends, HTTPException, Query, status
from pydantic import BaseModel
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.middleware.auth import get_current_user
from app.dependencies import get_db
from app.models.deal import Deal
from app.models.email_thread import EmailThread
from app.models.pipeline_config import PipelineConfig
from app.models.stage_recommendation import StageRecommendation
from app.models.user_config import UserConfig, UserRole

logger = structlog.get_logger()

router = APIRouter(prefix="/deals", tags=["Deals"])


# ---------- Response schemas ----------


class DealListItem(BaseModel):
    id: str
    hubspot_deal_id: str
    deal_name: str
    current_stage: str
    current_stage_name: str
    hubspot_pipeline_id: str
    owner_user_id: str | None = None
    amount: float | None = None
    close_date: str | None = None
    thread_count: int
    recommendation_count: int
    last_synced_at: str
    created_at: str
    updated_at: str

    class Config:
        from_attributes = True


class PaginatedDeals(BaseModel):
    items: list[DealListItem]
    total: int
    page: int
    page_size: int
    total_pages: int


class DealDetail(BaseModel):
    id: str
    hubspot_deal_id: str
    deal_name: str
    current_stage: str
    current_stage_name: str
    hubspot_pipeline_id: str
    pipeline_name: str | None = None
    pipeline_id: str | None = None
    owner_user_id: str | None = None
    contact_ids: list[str]
    amount: float | None = None
    close_date: str | None = None
    last_synced_at: str
    created_at: str
    updated_at: str

    class Config:
        from_attributes = True


# ---------- Routes ----------


@router.get("", response_model=PaginatedDeals)
async def list_deals(
    page: int = Query(1, ge=1, description="Page number"),
    page_size: int = Query(20, ge=1, le=100, description="Items per page"),
    pipeline_id: uuid.UUID | None = Query(None, description="Filter by pipeline config ID"),
    owner_id: uuid.UUID | None = Query(None, description="Filter by owner user ID"),
    has_threads: bool | None = Query(None, description="Filter deals with/without email threads"),
    db: AsyncSession = Depends(get_db),
    current_user: UserConfig = Depends(get_current_user),
) -> PaginatedDeals:
    """List deals with pagination and filters.

    Includes thread_count and recommendation_count as aggregate subqueries.
    Sales users see only their own deals; revops/admin see all.
    """
    # Subquery for thread count per deal
    thread_count_subq = (
        select(func.count(EmailThread.id))
        .where(EmailThread.deal_id == Deal.id)
        .correlate(Deal)
        .scalar_subquery()
        .label("thread_count")
    )

    # Subquery for recommendation count per deal
    rec_count_subq = (
        select(func.count(StageRecommendation.id))
        .where(StageRecommendation.deal_id == Deal.id)
        .correlate(Deal)
        .scalar_subquery()
        .label("recommendation_count")
    )

    query = select(Deal, thread_count_subq, rec_count_subq)

    # Role-based filtering: sales users only see their own deals
    if current_user.role == UserRole.SALES_USER:
        query = query.where(Deal.owner_user_id == current_user.id)

    # Apply filters
    if pipeline_id is not None:
        query = query.where(Deal.pipeline_id == pipeline_id)
    if owner_id is not None:
        query = query.where(Deal.owner_user_id == owner_id)
    if has_threads is True:
        # Filter to deals that have at least one thread
        threads_exist_subq = (
            select(func.count(EmailThread.id))
            .where(EmailThread.deal_id == Deal.id)
            .correlate(Deal)
            .scalar_subquery()
        )
        query = query.where(threads_exist_subq > 0)
    elif has_threads is False:
        threads_exist_subq = (
            select(func.count(EmailThread.id))
            .where(EmailThread.deal_id == Deal.id)
            .correlate(Deal)
            .scalar_subquery()
        )
        query = query.where(threads_exist_subq == 0)

    # Count total before pagination
    count_query = select(func.count()).select_from(query.subquery())
    total_result = await db.execute(count_query)
    total = total_result.scalar_one()

    # Order and paginate
    query = query.order_by(Deal.updated_at.desc())
    offset = (page - 1) * page_size
    query = query.offset(offset).limit(page_size)

    result = await db.execute(query)
    rows = result.all()

    items = [
        DealListItem(
            id=str(deal.id),
            hubspot_deal_id=deal.hubspot_deal_id,
            deal_name=deal.deal_name,
            current_stage=deal.current_stage,
            current_stage_name=deal.current_stage_name,
            hubspot_pipeline_id=deal.hubspot_pipeline_id,
            owner_user_id=str(deal.owner_user_id) if deal.owner_user_id else None,
            amount=float(deal.amount) if deal.amount is not None else None,
            close_date=deal.close_date.isoformat() if deal.close_date else None,
            thread_count=thread_count,
            recommendation_count=rec_count,
            last_synced_at=deal.last_synced_at.isoformat(),
            created_at=deal.created_at.isoformat(),
            updated_at=deal.updated_at.isoformat(),
        )
        for deal, thread_count, rec_count in rows
    ]

    total_pages = (total + page_size - 1) // page_size if total > 0 else 0

    await logger.ainfo(
        "deals_listed",
        total=total,
        page=page,
        page_size=page_size,
        actor=current_user.email,
    )

    return PaginatedDeals(
        items=items,
        total=total,
        page=page,
        page_size=page_size,
        total_pages=total_pages,
    )


@router.get("/{deal_id}", response_model=DealDetail)
async def get_deal(
    deal_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    current_user: UserConfig = Depends(get_current_user),
) -> DealDetail:
    """Get deal detail with pipeline name from PipelineConfig."""
    query = (
        select(Deal, PipelineConfig.pipeline_name)
        .join(PipelineConfig, Deal.pipeline_id == PipelineConfig.id, isouter=True)
        .where(Deal.id == deal_id)
    )

    # Sales users can only view their own deals
    if current_user.role == UserRole.SALES_USER:
        query = query.where(Deal.owner_user_id == current_user.id)

    result = await db.execute(query)
    row = result.one_or_none()

    if not row:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Deal not found",
        )

    deal, pipeline_name = row

    await logger.ainfo(
        "deal_detail_viewed",
        deal_id=str(deal.id),
        actor=current_user.email,
    )

    return DealDetail(
        id=str(deal.id),
        hubspot_deal_id=deal.hubspot_deal_id,
        deal_name=deal.deal_name,
        current_stage=deal.current_stage,
        current_stage_name=deal.current_stage_name,
        hubspot_pipeline_id=deal.hubspot_pipeline_id,
        pipeline_name=pipeline_name,
        pipeline_id=str(deal.pipeline_id) if deal.pipeline_id else None,
        owner_user_id=str(deal.owner_user_id) if deal.owner_user_id else None,
        contact_ids=[str(cid) for cid in (deal.contact_ids or [])],
        amount=float(deal.amount) if deal.amount is not None else None,
        close_date=deal.close_date.isoformat() if deal.close_date else None,
        last_synced_at=deal.last_synced_at.isoformat(),
        created_at=deal.created_at.isoformat(),
        updated_at=deal.updated_at.isoformat(),
    )
