# ── Build Stage ───────────────────────────────────────────────
FROM python:3.11-slim AS builder

WORKDIR /build

# Install build dependencies
RUN pip install --no-cache-dir setuptools wheel

# Copy dependency specification first for layer caching
COPY pyproject.toml .
RUN pip install --no-cache-dir --prefix=/install .

# ── Runtime Stage ─────────────────────────────────────────────
FROM python:3.11-slim

WORKDIR /app

# Create non-root user
RUN groupadd --gid 1001 appuser && \
    useradd --uid 1001 --gid appuser --shell /bin/bash --create-home appuser

# Copy installed packages from builder
COPY --from=builder /install /usr/local

# Copy application code
COPY alembic/ alembic/
COPY alembic.ini .
COPY app/ app/

# Switch to non-root user
USER appuser

# Expose API port
EXPOSE 8000

# Health check
HEALTHCHECK --interval=30s --timeout=5s --start-period=10s --retries=3 \
    CMD python -c "import urllib.request; urllib.request.urlopen('http://localhost:8000/api/v1/health/ready')" || exit 1

# Start the application
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]
