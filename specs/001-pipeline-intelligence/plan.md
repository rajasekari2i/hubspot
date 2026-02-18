# Implementation Plan: HubSpot Pipeline Intelligence

**Branch**: `001-pipeline-intelligence` | **Date**: 2026-02-15 | **Spec**: [spec.md](./spec.md)
**Input**: Feature specification from `/specs/001-pipeline-intelligence/spec.md`

## Summary

Build an intelligence layer that monitors sales email via Gmail push
notifications, classifies deal-progression signals using LLM-based
intent analysis (Claude Haiku 4.5), generates human-reviewed
recommendations delivered via Slack interactive messages and a web
dashboard, and writes approved stage changes back to HubSpot. Phase 1
is a human-in-the-loop pilot for 10-20 internal users over 12 weeks.

The backend is a Python/FastAPI monolith with modular services
(ingestion, classification, recommendation, notification, CRM update)
running as a single Cloud Run instance. The frontend is a Next.js 14
dashboard for RevOps analytics, alternative approval, and admin
configuration. PostgreSQL stores all persistent state; Redis provides
caching, rate limiting, and DLQ buffering.

## Technical Context

**Language/Version**: Python 3.11+ (backend), TypeScript 5.x (dashboard)
**Primary Dependencies**: FastAPI 0.110+, SQLAlchemy 2.0+, Alembic,
APScheduler, google-cloud-pubsub, google-api-python-client,
hubspot-api-client, anthropic SDK, openai SDK, slack-sdk, redis-py,
cryptography (AES-256), prometheus-client; Next.js 14, Tailwind CSS 3.x
**Storage**: PostgreSQL 15+ (primary), Redis 7+ (cache/rate-limit/DLQ)
**Testing**: pytest + pytest-cov + pytest-asyncio (backend),
Jest + React Testing Library (dashboard)
**Target Platform**: Linux containers on GCP Cloud Run
**Project Type**: Web application (backend + frontend)
**Performance Goals**: Email-to-notification p50 < 60s, p95 < 120s;
Approval-to-CRM-write p50 < 3s, p95 < 10s
**Constraints**: ~1,000 emails/day, 10-20 users, HubSpot rate limit
110 req/10s (OAuth), single instance (pilot)
**Scale/Scope**: Pilot: 10-20 users, ~500-1,000 emails/day,
~2,000-5,000 HubSpot API calls/day. Design must not preclude
horizontal scaling to 500+ users.

## Constitution Check

*GATE: Must pass before Phase 0 research. Re-check after Phase 1 design.*

| # | Principle | Status | Evidence |
|---|-----------|--------|----------|
| I | Human-in-the-Loop | PASS | All CRM writes gated by explicit user approval (FR-014, FR-015, FR-017). No auto-approve code path. Expiration instead of auto-approve (FR-019). |
| II | Data Privacy & Minimization | PASS | No email body storage (FR-025). PII redaction before LLM (FR-024). Retention policies defined (spec Assumptions). GDPR deletion supported (FR-026). |
| III | Auditability & Explainability | PASS | Immutable audit log for all state transitions (FR-022). Decision Trail view (FR-023). Prompt version recorded per classification (FR-027). |
| IV | Resilience & Zero Data Loss | PASS | At-least-once Pub/Sub delivery with ack-after-persist. Exponential backoff + DLQ for all external calls. Circuit breakers for Gmail, HubSpot, LLM, Slack. |
| V | Security by Default | PASS | AES-256 token encryption. TLS 1.2+ for all external calls. Proactive token refresh. RBAC at API layer (FR-028). Slack signature verification. GCP Secret Manager in prod. |
| VI | Modular Architecture | PASS | Distinct service modules with protocol-based interfaces. All integrations behind ABCs. Config hierarchy: env -> DB -> defaults. Alembic migrations. |
| VII | Observability | PASS | Structured JSON logs with trace_id. Prometheus metrics. Slack alerting for DLQ, error rates, watch renewal, inactivity. |

**Gate result**: ALL PASS. No violations. Proceeding to Phase 0.

## Project Structure

### Documentation (this feature)

```text
specs/001-pipeline-intelligence/
├── plan.md              # This file
├── research.md          # Phase 0 output
├── data-model.md        # Phase 1 output
├── quickstart.md        # Phase 1 output
├── contracts/           # Phase 1 output (OpenAPI specs)
│   ├── api.yaml         # Backend REST API
│   └── webhooks.yaml    # Inbound webhook contracts
└── tasks.md             # Phase 2 output (/speckit.tasks)
```

### Source Code (repository root)

```text
backend/
├── app/
│   ├── main.py                          # FastAPI entry point
│   ├── config.py                        # Settings (env/DB/defaults)
│   ├── dependencies.py                  # DI container
│   ├── api/
│   │   ├── routes/
│   │   │   ├── recommendations.py       # Recommendation CRUD + approval
│   │   │   ├── deals.py                 # Deal views
│   │   │   ├── admin.py                 # Admin config endpoints
│   │   │   ├── auth.py                  # OIDC auth flow
│   │   │   ├── slack_interactions.py    # Slack webhook handler
│   │   │   ├── audit.py                 # Audit trail queries
│   │   │   └── health.py               # Health + readiness checks
│   │   └── middleware/
│   │       ├── auth.py                  # OIDC + RBAC middleware
│   │       ├── logging.py              # Request/response logging
│   │       └── trace.py                # trace_id propagation
│   ├── services/
│   │   ├── ingestion.py                 # Email fetch + persist
│   │   ├── thread_linker.py             # Email -> Contact -> Deal
│   │   ├── intent_analyzer.py           # LLM classification orchestration
│   │   ├── stage_mapper.py              # Intent -> Stage mapping
│   │   ├── recommendation.py            # Recommendation generation
│   │   ├── notification.py              # Slack message delivery
│   │   ├── crm_updater.py              # HubSpot deal writes
│   │   ├── audit.py                     # Audit log writer
│   │   └── pii_redactor.py             # PII redaction before LLM
│   ├── integrations/
│   │   ├── gmail/
│   │   │   ├── client.py               # Gmail API wrapper
│   │   │   └── protocol.py             # EmailProvider ABC
│   │   ├── hubspot/
│   │   │   ├── client.py               # HubSpot API wrapper
│   │   │   └── protocol.py             # CRMProvider ABC
│   │   ├── llm/
│   │   │   ├── base.py                 # LLMProvider ABC
│   │   │   ├── anthropic.py            # Claude implementation
│   │   │   └── openai.py              # GPT fallback implementation
│   │   └── slack/
│   │       ├── client.py               # Slack API wrapper
│   │       └── protocol.py             # MessagingProvider ABC
│   ├── models/                          # SQLAlchemy ORM models
│   │   ├── base.py                     # Base model + mixins
│   │   ├── email_message.py
│   │   ├── email_thread.py
│   │   ├── deal.py
│   │   ├── stage_recommendation.py
│   │   ├── intent_classification.py
│   │   ├── audit_log.py
│   │   ├── user_config.py
│   │   ├── credential.py
│   │   ├── pipeline_config.py
│   │   ├── prompt_version.py
│   │   └── dead_message.py
│   ├── workers/
│   │   ├── pubsub_consumer.py          # Pub/Sub pull worker
│   │   ├── watch_renewer.py            # Gmail watch renewal (daily)
│   │   ├── dlq_processor.py            # Dead letter queue retry
│   │   ├── token_refresher.py          # OAuth token proactive refresh
│   │   ├── expiration_worker.py        # Recommendation expiration
│   │   └── pipeline_sync.py           # HubSpot pipeline metadata sync
│   └── utils/
│       ├── encryption.py               # AES-256 encrypt/decrypt
│       ├── rate_limiter.py             # Redis token bucket
│       ├── circuit_breaker.py          # Circuit breaker pattern
│       └── retry.py                    # Exponential backoff + jitter
├── alembic/
│   ├── alembic.ini
│   └── versions/
├── tests/
│   ├── conftest.py
│   ├── unit/
│   │   ├── services/
│   │   ├── utils/
│   │   └── models/
│   ├── integration/
│   │   ├── test_gmail_client.py
│   │   ├── test_hubspot_client.py
│   │   ├── test_llm_clients.py
│   │   ├── test_slack_client.py
│   │   └── test_pipeline_flow.py
│   └── contract/
│       └── test_api_routes.py
├── pyproject.toml
├── Dockerfile
└── .env.example

dashboard/
├── src/
│   ├── app/
│   │   ├── layout.tsx
│   │   ├── page.tsx                    # Dashboard home
│   │   ├── (auth)/
│   │   │   ├── login/page.tsx
│   │   │   └── callback/page.tsx
│   │   ├── dashboard/
│   │   │   ├── recommendations/
│   │   │   │   ├── page.tsx            # Recommendation list
│   │   │   │   └── [id]/page.tsx       # Decision trail detail
│   │   │   ├── analytics/
│   │   │   │   └── page.tsx            # KPI dashboard
│   │   │   ├── deals/
│   │   │   │   └── page.tsx            # Deal overview
│   │   │   └── admin/
│   │   │       ├── users/page.tsx
│   │   │       ├── pipelines/page.tsx
│   │   │       ├── prompts/page.tsx
│   │   │       ├── thresholds/page.tsx
│   │   │       └── health/page.tsx
│   │   └── api/                        # Next.js API routes (BFF)
│   ├── components/
│   │   ├── ui/                         # Shared UI primitives
│   │   ├── recommendations/            # Recommendation cards, trail
│   │   ├── analytics/                  # Charts, metric cards
│   │   └── admin/                      # Config forms
│   ├── lib/
│   │   ├── api-client.ts              # Backend API client
│   │   └── auth.ts                    # OIDC session management
│   └── types/
│       └── index.ts                   # Shared TypeScript types
├── tests/
│   └── components/
├── package.json
├── tsconfig.json
├── tailwind.config.ts
├── next.config.js
└── Dockerfile

infra/
├── terraform/
│   ├── main.tf
│   ├── variables.tf
│   ├── cloud-run.tf
│   ├── cloud-sql.tf
│   ├── memorystore.tf
│   ├── pubsub.tf
│   └── secrets.tf
└── docker-compose.yml                  # Local development
```

**Structure Decision**: Web application layout (Option 2 expanded).
Backend is a Python/FastAPI monolith with modular services. Dashboard
is a Next.js 14 app serving as the admin UI, analytics dashboard, and
alternative approval interface. Infrastructure-as-code via Terraform
in `infra/`. This matches the PRD Appendix B structure with minor
organizational refinements.

## Complexity Tracking

> No constitution violations detected. No complexity justifications needed.
