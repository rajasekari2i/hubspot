"""Trace ID propagation middleware."""

import uuid

import structlog
from starlette.middleware.base import BaseHTTPMiddleware, RequestResponseEndpoint
from starlette.requests import Request
from starlette.responses import Response

logger = structlog.get_logger()

TRACE_ID_HEADER = "X-Trace-ID"


class TraceMiddleware(BaseHTTPMiddleware):
    """Generate or propagate a trace_id UUID for each request."""

    async def dispatch(self, request: Request, call_next: RequestResponseEndpoint) -> Response:
        # Use incoming trace ID or generate a new one
        trace_id = request.headers.get(TRACE_ID_HEADER) or str(uuid.uuid4())
        request.state.trace_id = trace_id

        # Bind trace_id to structlog context for all downstream logging
        structlog.contextvars.clear_contextvars()
        structlog.contextvars.bind_contextvars(trace_id=trace_id)

        response = await call_next(request)
        response.headers[TRACE_ID_HEADER] = trace_id
        return response
