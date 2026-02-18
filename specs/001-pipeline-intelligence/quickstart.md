# Quickstart: HubSpot Pipeline Intelligence

**Date**: 2026-02-15

## Prerequisites

- Python 3.11+
- Node.js 20+ and npm
- Docker and Docker Compose
- GCP project with Pub/Sub enabled
- Gmail API credentials (OAuth client ID)
- HubSpot private app token (or OAuth credentials)
- Slack app with bot token and signing secret
- Anthropic API key (Claude Haiku 4.5)
- OpenAI API key (GPT-4o-mini fallback)

## 1. Clone and Setup

```bash
git clone <repo-url>
cd hubspot-pipeline-intelligence
```

## 2. Start Infrastructure (PostgreSQL + Redis)

```bash
docker compose up -d postgres redis
```

This starts:
- PostgreSQL 15 on `localhost:5432`
- Redis 7 on `localhost:6379`

## 3. Backend Setup

```bash
cd backend

# Create virtual environment
python -m venv .venv
source .venv/bin/activate

# Install dependencies
pip install -e ".[dev]"

# Copy environment config
cp .env.example .env
# Edit .env with your credentials (see Environment Variables below)

# Run database migrations
alembic upgrade head

# Seed initial data (default prompt version, pipeline config)
python -m app.scripts.seed

# Start the backend (development mode)
uvicorn app.main:app --reload --port 8000
```

The API is available at `http://localhost:8000`.
API docs at `http://localhost:8000/docs`.

## 4. Dashboard Setup

```bash
cd dashboard

# Install dependencies
npm install

# Copy environment config
cp .env.example .env.local
# Edit .env.local (set NEXT_PUBLIC_API_URL=http://localhost:8000/api/v1)

# Start development server
npm run dev
```

The dashboard is available at `http://localhost:3000`.

## 5. Start Background Workers

In a separate terminal (with backend venv activated):

```bash
cd backend

# Start the Pub/Sub consumer
python -m app.workers.pubsub_consumer &

# Start the scheduler (watch renewal, DLQ, token refresh, expiration)
python -m app.workers.scheduler &
```

## 6. Configure External Services

### Gmail

1. Create a GCP OAuth 2.0 Client ID (Desktop or Web type)
2. Enable Gmail API in your GCP project
3. Create Pub/Sub topic `gmail-push-notifications`
4. Grant `gmail-api-push@system.gserviceaccount.com` Publisher role
5. Create a pull subscription for the topic
6. Set `GOOGLE_CLOUD_PROJECT`, `PUBSUB_SUBSCRIPTION` in `.env`

### HubSpot

1. Create a private app in HubSpot Developer portal
2. Grant scopes: `crm.objects.deals.read`, `crm.objects.deals.write`,
   `crm.objects.contacts.read`, `crm.schemas.deals.read`,
   `crm.objects.owners.read`
3. Copy the access token to `HUBSPOT_ACCESS_TOKEN` in `.env`

### Slack

1. Create a Slack app at api.slack.com
2. Add bot scopes: `chat:write`, `chat:write.public`,
   `users:read`, `users:read.email`
3. Install to workspace
4. Set the interaction URL to `{your-url}/api/v1/slack/interactions`
5. Copy Bot Token and Signing Secret to `.env`

### LLM Providers

1. Get an Anthropic API key from console.anthropic.com
2. Get an OpenAI API key from platform.openai.com
3. Set `ANTHROPIC_API_KEY` and `OPENAI_API_KEY` in `.env`

## Environment Variables

```bash
# Database
DATABASE_URL=postgresql+asyncpg://postgres:postgres@localhost:5432/pipeline_intelligence

# Redis
REDIS_URL=redis://localhost:6379/0

# Gmail / GCP
GOOGLE_CLOUD_PROJECT=your-gcp-project
PUBSUB_SUBSCRIPTION=gmail-push-sub
GOOGLE_CLIENT_ID=your-oauth-client-id
GOOGLE_CLIENT_SECRET=your-oauth-client-secret

# HubSpot
HUBSPOT_ACCESS_TOKEN=your-private-app-token

# Slack
SLACK_BOT_TOKEN=xoxb-your-bot-token
SLACK_SIGNING_SECRET=your-signing-secret
SLACK_ALERT_CHANNEL=#pipeline-intelligence-alerts

# LLM
ANTHROPIC_API_KEY=sk-ant-your-key
OPENAI_API_KEY=sk-your-key
LLM_PRIMARY_PROVIDER=anthropic
LLM_FALLBACK_PROVIDER=openai
LLM_PRIMARY_MODEL=claude-haiku-4-5-20251001
LLM_FALLBACK_MODEL=gpt-4o-mini

# Encryption
ENCRYPTION_KEY=your-32-byte-base64-key

# Auth (OIDC)
OIDC_ISSUER=https://accounts.google.com
OIDC_CLIENT_ID=your-oidc-client-id
OIDC_CLIENT_SECRET=your-oidc-client-secret
OIDC_REDIRECT_URI=http://localhost:8000/api/v1/auth/callback
SESSION_SECRET=your-session-secret

# App
APP_ENV=development
LOG_LEVEL=DEBUG
```

## 7. Verify Installation

```bash
# Check health endpoint
curl http://localhost:8000/api/v1/health | python -m json.tool

# Expected: all checks "ok" (except Gmail/HubSpot if not configured)
```

## 8. Run Tests

```bash
# Backend unit tests
cd backend
pytest tests/unit -v --cov=app --cov-report=term-missing

# Backend integration tests (requires running Docker services)
pytest tests/integration -v

# Dashboard tests
cd dashboard
npm test
```

## 9. Local Development with Docker Compose

For a fully containerized local environment:

```bash
docker compose up --build
```

This starts all services: backend, dashboard, PostgreSQL, Redis,
and worker processes.

## Common Development Tasks

### Add a new database migration

```bash
cd backend
alembic revision --autogenerate -m "description of change"
alembic upgrade head
```

### Add a new user (CLI)

```bash
cd backend
python -m app.scripts.add_user \
  --email user@company.com \
  --name "Sarah Rep" \
  --role sales_user \
  --hubspot-owner-id 12345 \
  --slack-user-id U12345
```

### Test the pipeline manually

1. Ensure a user is configured with Gmail watch active
2. Send an email to/from a contact linked to a HubSpot deal
3. Watch the backend logs for processing
4. Check Slack for the recommendation notification
5. Approve in Slack and verify the HubSpot deal stage updated
