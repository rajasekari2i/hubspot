# HubSpot Pipeline Intelligence

An intelligence layer that monitors sales emails via Gmail push notifications, classifies deal-progression signals using LLM-based intent analysis, generates human-reviewed stage recommendations delivered via Slack, and writes approved changes back to HubSpot CRM.

## Architecture

```mermaid
graph TB
    subgraph External Services
        Gmail[Gmail API]
        PubSub[Google Cloud<br/>Pub/Sub]
        HubSpot[HubSpot CRM<br/>API v3]
        SlackAPI[Slack API]
        Claude[Anthropic<br/>Claude Haiku 4.5]
        GPT[OpenAI<br/>GPT-4o-mini]
    end

    subgraph Backend ["Backend (FastAPI / Python 3.11)"]
        API[REST API<br/>:8000]
        MW[Middleware<br/>Auth / Logging / Trace]

        subgraph Workers
            PSC[Pub/Sub<br/>Consumer]
            WR[Watch<br/>Renewer]
            EXP[Expiration<br/>Worker]
            TR[Token<br/>Refresher]
            DLQ[DLQ<br/>Processor]
            PS[Pipeline<br/>Sync]
        end

        subgraph Services
            ING[Ingestion]
            TL[Thread Linker]
            IA[Intent Analyzer]
            SM[Stage Mapper]
            REC[Recommendation]
            NOT[Notification]
            CRM[CRM Updater]
            PII[PII Redactor]
            AUD[Audit Service]
        end

        subgraph Integrations
            GC[Gmail Client]
            HC[HubSpot Client]
            LLM[LLM Orchestrator]
            SC[Slack Client]
        end
    end

    subgraph Dashboard ["Dashboard (Next.js 14 / TypeScript)"]
        RPage[Recommendations]
        APage[Analytics]
        DPage[Deals]
        Admin[Admin Panel]
    end

    subgraph Data ["Data Layer"]
        PG[(PostgreSQL 15)]
        RD[(Redis 7)]
    end

    Gmail -- push notification --> PubSub
    PubSub --> PSC
    PSC --> ING
    ING --> GC --> Gmail
    ING --> TL
    TL --> HC --> HubSpot
    TL --> RD
    IA --> PII --> LLM
    LLM --> Claude
    LLM -.fallback.-> GPT
    SM --> PG
    REC --> PG
    NOT --> SC --> SlackAPI
    CRM --> HC
    AUD --> PG

    API --> MW --> Services
    Dashboard -- HTTP --> API
    SlackAPI -- interactions --> API

    Services --> PG
    Services --> RD
    WR --> GC
    PS --> HC
    TR --> PG
    DLQ --> RD
    EXP --> PG
```

## Pipeline Flow

```mermaid
sequenceDiagram
    participant Rep as Sales Rep
    participant Gmail as Gmail
    participant PubSub as Pub/Sub
    participant Worker as Pub/Sub Worker
    participant Ingest as Ingestion
    participant Linker as Thread Linker
    participant HubSpot as HubSpot API
    participant PII as PII Redactor
    participant LLM as LLM (Claude)
    participant Mapper as Stage Mapper
    participant RecSvc as Recommendation
    participant Slack as Slack
    participant DB as PostgreSQL
    participant CRM as CRM Updater

    Rep->>Gmail: Send/receive sales email
    Gmail->>PubSub: Push notification (historyId)
    PubSub->>Worker: Pull message
    Worker->>Ingest: Process notification

    Note over Ingest: Fetch new messages via<br/>Gmail history.list

    Ingest->>DB: Persist email metadata
    Ingest->>Linker: Link thread to deal

    Linker->>HubSpot: Search contacts by email
    HubSpot-->>Linker: Contact + associated deals
    Linker->>DB: Create/update email_thread

    Note over PII: Strip signatures,<br/>redact phone/SSN/CC

    Linker->>PII: Prepare email for classification
    PII->>LLM: Classify intent (structured JSON)
    LLM-->>PII: {intent, confidence, reasoning, direction}

    alt Confidence >= threshold
        PII->>Mapper: Map intent to stage
        Mapper->>DB: Lookup pipeline rules
        Mapper-->>RecSvc: Recommended stage

        RecSvc->>DB: Create stage_recommendation
        RecSvc->>Slack: Send Block Kit message
        Slack-->>Rep: Notification with Approve/Reject/Snooze
    else Below threshold
        PII->>DB: Log low-confidence classification
        Note over DB: Available in dashboard<br/>for RevOps review
    end

    rect rgb(230, 245, 230)
        Note over Rep,DB: Approval Flow
        Rep->>Slack: Tap Approve
        Slack->>CRM: Trigger writeback
        CRM->>HubSpot: Read current stage (conflict check)
        HubSpot-->>CRM: Current stage confirmed

        alt No conflict
            CRM->>HubSpot: PATCH deal stage + add note
            CRM->>DB: Update status → write_success
            CRM->>Slack: Update message (approved)
            CRM->>DB: Audit log entry
        else Stage conflict
            CRM->>DB: Update status → conflict
            CRM->>Slack: Update message (conflict warning)
        end
    end
```

## Recommendation State Machine

```mermaid
stateDiagram-v2
    [*] --> pending : Created

    pending --> approved : User approves
    pending --> rejected : User rejects (with reason)
    pending --> snoozed : User snoozes
    pending --> expired : Timeout reached
    pending --> superseded : Newer recommendation

    snoozed --> pending : Re-notify
    snoozed --> expired : Max snoozes (2) reached

    approved --> write_success : CRM updated
    approved --> write_failed : API error
    approved --> conflict : Stage changed externally

    write_success --> [*]
    write_failed --> [*]
    conflict --> [*]
    rejected --> [*]
    expired --> [*]
    superseded --> [*]
```

## Data Model

```mermaid
erDiagram
    user_configs ||--o{ email_messages : "monitors"
    user_configs ||--o{ credentials : "has"
    user_configs ||--o{ deals : "owns"
    email_messages }o--|| email_threads : "belongs to"
    email_threads }o--o| deals : "linked to"
    deals }o--|| pipeline_configs : "in pipeline"
    email_messages ||--o{ intent_classifications : "classified"
    email_messages ||--o{ stage_recommendations : "triggers"
    stage_recommendations }o--|| deals : "for deal"
    stage_recommendations }o--|| email_threads : "in thread"

    user_configs {
        uuid id PK
        varchar email UK
        varchar display_name
        enum role "admin/revops/sales_user"
        varchar hubspot_owner_id
        varchar slack_user_id
        boolean is_active
    }

    email_messages {
        uuid id PK
        varchar gmail_message_id UK
        varchar gmail_thread_id
        uuid user_id FK
        varchar subject
        enum processing_status "pending/processing/classified/failed"
        uuid trace_id
    }

    email_threads {
        uuid id PK
        varchar gmail_thread_id UK
        uuid deal_id FK
        decimal link_confidence
        varchar link_method
    }

    deals {
        uuid id PK
        varchar hubspot_deal_id UK
        uuid pipeline_id FK
        varchar current_stage
        varchar deal_name
        decimal amount
    }

    intent_classifications {
        uuid id PK
        uuid email_message_id FK
        uuid deal_id FK
        varchar intent
        decimal confidence_score "0.000-1.000"
        enum direction "forward/backward/neutral"
        varchar llm_model
    }

    stage_recommendations {
        uuid id PK
        uuid deal_id FK
        varchar current_stage
        varchar recommended_stage
        decimal confidence_score
        enum status "pending/approved/rejected/expired/..."
        timestamptz expires_at
        varchar idempotency_key UK
    }

    pipeline_configs {
        uuid id PK
        varchar hubspot_pipeline_id UK
        jsonb stages
        jsonb intent_to_stage_rules
        decimal recommendation_threshold
        integer approval_timeout_hours
    }

    prompt_versions {
        uuid id PK
        varchar version UK
        text prompt_template
        text system_prompt
        jsonb intent_categories
        boolean is_active "partial unique"
    }

    audit_logs {
        uuid id PK
        uuid trace_id
        varchar action
        varchar entity_type
        uuid entity_id
        enum actor_type "system/user"
        jsonb before_state
        jsonb after_state
    }
```

## How It Works

1. **Email Monitoring** - Gmail push notifications detect new sales emails via Pub/Sub
2. **Thread Linking** - Emails are matched to HubSpot deals through contact resolution
3. **Intent Classification** - Claude Haiku 4.5 classifies the email's deal-progression intent (e.g., pricing discussion, contract negotiation, technical evaluation)
4. **Recommendation** - If confidence exceeds the threshold, a stage change recommendation is generated
5. **Slack Notification** - Sales reps receive an interactive Slack message with Approve/Reject/Snooze buttons
6. **CRM Writeback** - Approved recommendations update the deal stage in HubSpot with audit notes
7. **Dashboard** - RevOps can monitor recommendations, view analytics, and manage configuration

## Tech Stack

| Component | Technology |
|-----------|-----------|
| Backend API | Python 3.11+, FastAPI, SQLAlchemy 2.0, Alembic |
| Dashboard | Next.js 14, TypeScript 5.x, Tailwind CSS 3.x |
| Database | PostgreSQL 15+ |
| Cache/Queue | Redis 7+ |
| LLM (primary) | Anthropic Claude Haiku 4.5 |
| LLM (fallback) | OpenAI GPT-4o-mini |
| Email | Gmail API + Google Cloud Pub/Sub |
| CRM | HubSpot API v3 |
| Notifications | Slack Block Kit |
| Metrics | Prometheus |
| Deployment | Docker, GCP Cloud Run |

## Project Structure

```
backend/
├── app/
│   ├── main.py                 # FastAPI entry point
│   ├── config.py               # Settings (env/DB/defaults)
│   ├── dependencies.py         # DI container
│   ├── api/
│   │   ├── routes/             # REST endpoints
│   │   │   ├── recommendations.py
│   │   │   ├── deals.py
│   │   │   ├── analytics.py
│   │   │   ├── admin.py
│   │   │   ├── auth.py
│   │   │   ├── slack_interactions.py
│   │   │   ├── audit.py
│   │   │   └── health.py
│   │   └── middleware/         # Auth, logging, tracing
│   ├── services/               # Business logic
│   ├── integrations/           # Gmail, HubSpot, LLM, Slack clients
│   ├── models/                 # SQLAlchemy ORM models
│   ├── workers/                # Background workers
│   └── utils/                  # Encryption, rate limiter, circuit breaker
├── alembic/                    # Database migrations
├── Dockerfile
└── pyproject.toml

dashboard/
├── src/
│   ├── app/
│   │   └── dashboard/
│   │       ├── recommendations/ # Recommendation list & detail
│   │       ├── analytics/       # KPI dashboard
│   │       ├── deals/           # Deal overview
│   │       └── admin/           # Users, pipelines, prompts, thresholds, health
│   ├── lib/                     # API client, auth
│   └── types/                   # Shared TypeScript types
├── Dockerfile
└── package.json

infra/
└── docker-compose.yml           # PostgreSQL, Redis, backend, dashboard, workers
```

## Getting Started

### Prerequisites

- Python 3.11+
- Node.js 20+ and npm
- Docker and Docker Compose

### 1. Start Infrastructure

```bash
cd infra
docker compose up -d postgres redis
```

### 2. Backend Setup

```bash
cd backend
python -m venv .venv
source .venv/bin/activate
pip install -e ".[dev]"

cp .env.example .env
# Edit .env with your credentials

alembic upgrade head
python -m app.scripts.seed
uvicorn app.main:app --reload --port 8000
```

API available at `http://localhost:8000` (docs at `/docs`).

### 3. Dashboard Setup

```bash
cd dashboard
npm install

cp .env.example .env.local
# Set NEXT_PUBLIC_API_URL=http://localhost:8000/api/v1

npm run dev
```

Dashboard available at `http://localhost:3000`.

### 4. Start Workers

```bash
cd backend
python -m app.workers.pubsub_consumer &
```

### 5. Run with Docker Compose (all services)

```bash
cd infra
docker compose up --build
```

## External Services Setup

| Service | What's Needed |
|---------|--------------|
| **Gmail** | GCP OAuth Client ID, Gmail API enabled, Pub/Sub topic `gmail-push-notifications` |
| **HubSpot** | Private app token with deal/contact/owner read+write scopes |
| **Slack** | Bot token (`chat:write`, `users:read`), signing secret, interaction URL |
| **Anthropic** | API key for Claude Haiku 4.5 |
| **OpenAI** | API key for GPT-4o-mini (fallback) |

See `backend/.env.example` for all required environment variables.

## Key Endpoints

| Method | Path | Description |
|--------|------|-------------|
| GET | `/api/v1/health` | System health check |
| GET | `/api/v1/recommendations` | List recommendations (paginated, filterable) |
| POST | `/api/v1/recommendations/{id}/approve` | Approve a recommendation |
| POST | `/api/v1/recommendations/{id}/reject` | Reject with reason |
| GET | `/api/v1/deals` | List deals |
| GET | `/api/v1/analytics/overview` | Analytics KPIs |
| GET | `/api/v1/admin/users` | List users (admin) |
| GET | `/api/v1/admin/pipelines` | Pipeline configuration (admin) |
| GET | `/api/v1/admin/prompts` | Prompt versions (admin) |
| POST | `/api/v1/slack/interactions` | Slack webhook handler |
| GET | `/api/v1/metrics` | Prometheus metrics |

## Performance Targets

| Metric | Target |
|--------|--------|
| Email to Slack notification (p50) | < 60s |
| Email to Slack notification (p95) | < 120s |
| Approval to CRM write (p50) | < 3s |
| Approval to CRM write (p95) | < 10s |

## Architecture Principles

| Principle | Implementation |
|-----------|---------------|
| **Human-in-the-loop** | All CRM writes require explicit user approval; no auto-approve path exists |
| **Privacy by design** | No email body storage; PII redacted before LLM processing (phone, SSN, CC stripped) |
| **Resilience** | Per-integration circuit breakers, exponential backoff with jitter, Redis DLQ with DB overflow |
| **Audit trail** | Immutable INSERT-only audit log for every state transition with trace_id correlation |
| **LLM failover** | Primary (Claude Haiku 4.5) with automatic fallback to GPT-4o-mini on circuit break |
| **Configurable** | Thresholds, prompts, intent mappings, and timeouts adjustable via admin dashboard |
| **Observability** | Structured JSON logs (structlog), Prometheus metrics, Slack alerting for DLQ/errors |
| **Security** | AES-256 encrypted tokens, Google OIDC SSO, RBAC (admin/revops/sales_user), Slack signature verification |

## Running Tests

```bash
# Backend
cd backend
pytest tests/unit -v --cov=app

# Dashboard
cd dashboard
npm test
```

## License

Proprietary - Internal use only.
