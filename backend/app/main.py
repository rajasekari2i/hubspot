"""FastAPI application entry point."""

import structlog
from contextlib import asynccontextmanager
from collections.abc import AsyncGenerator

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.api.middleware.trace import TraceMiddleware
from app.api.middleware.logging import LoggingMiddleware
from app.api.routes import admin, auth, health, recommendations, slack_interactions, deals, analytics, audit
from app.config import get_settings
from app.dependencies import close_connections

# Configure structlog for JSON output
structlog.configure(
    processors=[
        structlog.contextvars.merge_contextvars,
        structlog.processors.add_log_level,
        structlog.processors.TimeStamper(fmt="iso"),
        structlog.dev.ConsoleRenderer()
        if get_settings().is_development
        else structlog.processors.JSONRenderer(),
    ],
    logger_factory=structlog.PrintLoggerFactory(),
)

logger = structlog.get_logger()


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncGenerator[None, None]:
    """Application lifespan: startup and shutdown events."""
    await logger.ainfo("application_starting")
    yield
    await logger.ainfo("application_shutting_down")
    await close_connections()


def create_app() -> FastAPI:
    settings = get_settings()

    app = FastAPI(
        title="HubSpot Pipeline Intelligence",
        version="0.1.0",
        lifespan=lifespan,
    )

    # Middleware (order matters: outermost first)
    app.add_middleware(
        CORSMiddleware,
        allow_origins=["http://localhost:3000"],
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )
    app.add_middleware(LoggingMiddleware)
    app.add_middleware(TraceMiddleware)

    # Routes - Foundational
    app.include_router(health.router, prefix=settings.api_v1_prefix)
    app.include_router(auth.router, prefix=settings.api_v1_prefix)

    # Routes - US2: Approval & CRM Writeback
    app.include_router(recommendations.router, prefix=settings.api_v1_prefix)
    app.include_router(slack_interactions.router, prefix=settings.api_v1_prefix)

    # Routes - US3: Dashboard & Analytics
    app.include_router(deals.router, prefix=settings.api_v1_prefix)
    app.include_router(analytics.router, prefix=settings.api_v1_prefix)
    app.include_router(audit.router, prefix=settings.api_v1_prefix)

    # Routes - US4: Administration
    app.include_router(admin.router, prefix=settings.api_v1_prefix)

    return app


app = create_app()
