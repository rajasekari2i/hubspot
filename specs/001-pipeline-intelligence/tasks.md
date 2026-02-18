# Tasks: HubSpot Pipeline Intelligence

**Input**: Design documents from `/specs/001-pipeline-intelligence/`
**Prerequisites**: plan.md, spec.md, research.md, data-model.md, contracts/ (api.yaml, webhooks.yaml), quickstart.md

**Tests**: Not explicitly requested in the feature specification. Test tasks are omitted.

**Organization**: Tasks are grouped by user story to enable independent implementation and testing of each story.

## Format: `[ID] [P?] [Story] Description`

- **[P]**: Can run in parallel (different files, no dependencies on incomplete tasks)
- **[Story]**: Which user story this task belongs to (e.g., US1, US2, US3, US4)
- All file paths are relative to repository root

## Path Conventions

- **Backend**: `backend/app/` (Python/FastAPI)
- **Dashboard**: `dashboard/src/` (Next.js 14 / TypeScript)
- **Infrastructure**: `infra/` (Docker Compose, Terraform)
- **Migrations**: `backend/alembic/`

---

## Phase 1: Setup (Shared Infrastructure)

**Purpose**: Project initialization, directory scaffolding, and dependency configuration

- [x] T001 Create full project directory structure per plan.md (backend/, dashboard/, infra/ with all subdirectories)
- [x] T002 [P] Initialize backend Python project with pyproject.toml (FastAPI, SQLAlchemy, Alembic, APScheduler, google-cloud-pubsub, google-api-python-client, hubspot-api-client, anthropic, openai, slack-sdk, redis, cryptography, prometheus-client, structlog, pytest dev deps) in backend/pyproject.toml
- [x] T003 [P] Initialize Next.js 14 dashboard project with TypeScript 5.x, Tailwind CSS 3.x, and ESLint in dashboard/package.json
- [x] T004 [P] Create Docker Compose for local development (PostgreSQL 15 on :5432, Redis 7 on :6379) in infra/docker-compose.yml
- [x] T005 [P] Create .env.example files with all required environment variables per quickstart.md in backend/.env.example and dashboard/.env.example

---

## Phase 2: Foundational (Blocking Prerequisites)

**Purpose**: Core infrastructure that MUST be complete before ANY user story can be implemented

**CRITICAL**: No user story work can begin until this phase is complete

- [x] T006 Implement Pydantic Settings class with env/DB/defaults config hierarchy in backend/app/config.py
- [x] T007 [P] Create SQLAlchemy async base model with TimestampMixin (created_at, updated_at) in backend/app/models/base.py
- [x] T008 [P] Setup Alembic with async PostgreSQL support (alembic.ini, env.py) in backend/alembic/
- [x] T009 [P] Implement AES-256 encrypt/decrypt utility using cryptography library in backend/app/utils/encryption.py
- [x] T010 [P] Implement exponential backoff with jitter retry utility (base * 2^attempt + random, capped at max) in backend/app/utils/retry.py
- [x] T011 [P] Implement per-integration circuit breaker (configurable failure threshold, half-open timer) in backend/app/utils/circuit_breaker.py
- [x] T012 [P] Implement Redis-backed token bucket rate limiter (configurable req/window) in backend/app/utils/rate_limiter.py
- [x] T013 [P] Create UserConfig ORM model (email, display_name, role enum, hubspot_owner_id, slack_user_id, gmail_watch_expiration, is_active) in backend/app/models/user_config.py
- [x] T014 [P] Create Credential ORM model (user FK, provider enum, AES-256 encrypted tokens, token_expiry, scopes) in backend/app/models/credential.py
- [x] T015 [P] Create PipelineConfig ORM model (hubspot_pipeline_id, stages JSONB, intent_to_stage_rules JSONB, thresholds, timeout) in backend/app/models/pipeline_config.py
- [x] T016 [P] Create PromptVersion ORM model (version, prompt_template, system_prompt, intent_categories JSONB, is_active partial unique) in backend/app/models/prompt_version.py
- [x] T017 [P] Create Deal ORM model (hubspot_deal_id, pipeline FK, current_stage, deal_name, owner FK, amount, close_date, last_synced_at) in backend/app/models/deal.py
- [x] T018 [P] Create AuditLog ORM model (trace_id, action, entity_type, entity_id, actor_type enum, before/after JSONB, immutable INSERT-only) in backend/app/models/audit_log.py
- [x] T019 [P] Create DeadMessage ORM model (component, original_payload JSONB, error_message, retry_count, resolved flag) in backend/app/models/dead_message.py
- [x] T020 Generate initial Alembic migration for all foundational models (user_configs, credentials, pipeline_configs, prompt_versions, deals, audit_logs, dead_messages) in backend/alembic/versions/
- [x] T021 [P] Define integration protocol ABCs: EmailProvider in backend/app/integrations/gmail/protocol.py, CRMProvider in backend/app/integrations/hubspot/protocol.py, LLMProvider in backend/app/integrations/llm/base.py, MessagingProvider in backend/app/integrations/slack/protocol.py
- [x] T022 [P] Implement trace_id UUID propagation middleware (generate per request, attach to structlog context) in backend/app/api/middleware/trace.py
- [x] T023 [P] Implement structured JSON request/response logging middleware with structlog in backend/app/api/middleware/logging.py
- [x] T024 Implement Google OIDC authentication + role-based authorization middleware (admin, revops, sales_user) in backend/app/api/middleware/auth.py
- [x] T025 Implement auth routes (GET /login redirect, GET /callback token exchange, GET /me current user, POST /logout session clear) in backend/app/api/routes/auth.py
- [x] T026 [P] Implement health check (all dependency status) and readiness probe routes in backend/app/api/routes/health.py
- [x] T027 Implement audit log service (write immutable entries with trace_id, entity, actor, before/after state) in backend/app/services/audit.py
- [x] T028 Create DI container with async DB session factory, Redis client, Settings instance, and current_user dependency in backend/app/dependencies.py
- [x] T029 Create FastAPI app entry point with middleware stack (trace, logging, OIDC auth), CORS config, and foundational route registration (auth, health) in backend/app/main.py

**Checkpoint**: Foundation ready -- database, auth, middleware, utilities, and health checks operational. User story implementation can now begin.

---

## Phase 3: User Story 1 -- Email-Triggered Deal Stage Recommendations (Priority: P1) MVP

**Goal**: When a sales rep sends or receives a deal-related email, the system detects the progression signal via Gmail push notifications, classifies intent using Claude Haiku 4.5, and delivers a Slack recommendation within 2 minutes.

**Independent Test**: Send a sales email containing a pricing proposal to a contact linked to a HubSpot deal. Verify a Slack notification arrives within 2 minutes showing the correct deal name, current stage, recommended stage, confidence score, and reasoning.

### Models for User Story 1

- [x] T030 [P] [US1] Create EmailMessage ORM model (gmail_message_id, gmail_thread_id, gmail_history_id, user FK, from/to/cc addresses, subject, body_excerpt 500-char, processing_status enum, trace_id) in backend/app/models/email_message.py
- [x] T031 [P] [US1] Create EmailThread ORM model (gmail_thread_id, deal FK, contact_ids array, subject, message_count, link_confidence, link_method) in backend/app/models/email_thread.py
- [x] T032 [P] [US1] Create IntentClassification ORM model (email FK, deal FK, intent, confidence_score CHECK 0-1, reasoning, key_phrases array, direction enum, prompt_version, llm_model, latency, token counts, action_taken) in backend/app/models/intent_classification.py
- [x] T033 [P] [US1] Create StageRecommendation ORM model with state machine (pending->approved/rejected/expired/superseded/snoozed; approved->write_success/write_failed/conflict; snoozed->pending/expired) in backend/app/models/stage_recommendation.py
- [x] T034 [US1] Generate Alembic migration for US1 models (email_messages, email_threads, intent_classifications, stage_recommendations) with all indexes in backend/alembic/versions/

### Integration Clients for User Story 1

- [x] T035 [P] [US1] Implement Gmail API client (users.watch setup, history.list incremental sync, messages.get metadata+snippet, with circuit breaker and retry) in backend/app/integrations/gmail/client.py
- [x] T036 [P] [US1] Implement HubSpot API client read operations (search deals, get deal, search contacts by email, get owners, with rate limiter and circuit breaker) in backend/app/integrations/hubspot/client.py
- [x] T037 [P] [US1] Implement Anthropic Claude Haiku 4.5 client (structured JSON classification output, token tracking, circuit breaker) in backend/app/integrations/llm/anthropic.py
- [x] T038 [P] [US1] Implement OpenAI GPT-4o-mini fallback client (same structured output interface as Anthropic) in backend/app/integrations/llm/openai.py
- [x] T039 [US1] Implement LLM orchestrator with primary/fallback provider switching and circuit breaker integration in backend/app/integrations/llm/base.py
- [x] T040 [P] [US1] Implement Slack API client (chat.postMessage with Block Kit recommendation card: deal name, stages, confidence color-coded, Approve/Reject/Snooze buttons) in backend/app/integrations/slack/client.py

### Services for User Story 1

- [x] T041 [US1] Implement PII redactor (regex patterns for phone -> [PHONE], SSN/CC -> [REDACTED], email signature stripping; retain names and email addresses) in backend/app/services/pii_redactor.py
- [x] T042 [US1] Implement email ingestion service (fetch new messages via history.list, parse headers, persist metadata, update processing_status, audit log) in backend/app/services/ingestion.py
- [x] T043 [US1] Implement thread linker service (resolve email participants -> HubSpot contacts -> associated deals, Redis cache with 1h TTL, subject fuzzy matching for multi-deal, flag ambiguous) in backend/app/services/thread_linker.py
- [x] T044 [US1] Implement intent analyzer service (build context with deal stage + thread history, PII redact, call LLM, parse structured response, persist IntentClassification, audit log) in backend/app/services/intent_analyzer.py
- [x] T045 [US1] Implement stage mapper service (lookup intent_to_stage_rules from PipelineConfig, validate direction/ordering, enforce backward-only for regression intents) in backend/app/services/stage_mapper.py
- [x] T046 [US1] Implement recommendation generation service (check confidence threshold, check no duplicate pending, check stage differs from current, create StageRecommendation, supersede older pending, audit log) in backend/app/services/recommendation.py
- [x] T047 [US1] Implement notification service (format Slack Block Kit message with deal info, confidence badge, action buttons, send via Slack client, store slack_message_ts) in backend/app/services/notification.py

### Workers for User Story 1

- [x] T048 [US1] Implement Pub/Sub pull consumer worker (subscribe, ack-after-persist, orchestrate: ingest -> link thread -> classify intent -> map stage -> generate recommendation -> notify, error handling with DLQ) in backend/app/workers/pubsub_consumer.py
- [x] T049 [US1] Implement Gmail watch renewal scheduled worker (daily renewal for all active users, retry on failure, Slack alert on repeated failure, inactivity detector) in backend/app/workers/watch_renewer.py

### Seed Data for User Story 1

- [x] T050 [US1] Create seed script for default prompt version (v1.0.0 with 13 intent categories) and sample pipeline config in backend/app/scripts/seed.py

**Checkpoint**: Core pipeline operational -- emails detected, classified, and recommendations delivered via Slack. This is the MVP.

---

## Phase 4: User Story 2 -- Recommendation Approval & CRM Writeback (Priority: P2)

**Goal**: Sales reps can approve, reject (with corrective feedback), or snooze recommendations from Slack, and approved changes are written to HubSpot with full audit notes.

**Independent Test**: Given a pending recommendation in Slack, tap Approve and verify the HubSpot deal stage updates within 10 seconds with an audit note. Tap Reject on another, select a reason and corrected stage, verify the CRM updates and rejection is logged.

**Dependency**: Requires US1 complete (recommendations must exist to act upon)

### Services & Integrations for User Story 2

- [x] T051 [US2] Extend HubSpot client with write operations (update deal stage via PATCH, add deal note, read-before-write conflict check) in backend/app/integrations/hubspot/client.py
- [x] T052 [US2] Implement CRM updater service (read current stage, detect conflicts, update stage, add audit note with transition details, handle write failures, idempotency via idempotency_key) in backend/app/services/crm_updater.py
- [x] T053 [US2] Extend notification service with Slack message updates (replace buttons with approval confirmation, rejection details, expiration notice, conflict warning) in backend/app/services/notification.py

### API Routes for User Story 2

- [x] T054 [US2] Implement recommendation action API routes (POST /approve with CRM write trigger, POST /reject with reason + optional corrected_stage, POST /snooze with max-snooze enforcement) in backend/app/api/routes/recommendations.py
- [x] T055 [US2] Implement Slack interaction webhook handler (X-Slack-Signature verification, action dispatch for approve/reject/snooze/rejection_reason_selected/corrected_stage_selected) in backend/app/api/routes/slack_interactions.py

### Workers for User Story 2

- [x] T056 [US2] Implement recommendation expiration worker (query pending recommendations past expires_at, transition to expired, update Slack message, surface in dashboard, audit log) in backend/app/workers/expiration_worker.py

### Route Registration for User Story 2

- [x] T057 [US2] Register US2 routes (recommendations, slack_interactions) in backend/app/main.py

**Checkpoint**: Full approval loop operational -- recommendations can be approved/rejected/snoozed from Slack, CRM updates automatically, conflicts detected.

---

## Phase 5: User Story 3 -- Pipeline Monitoring & Analytics Dashboard (Priority: P3)

**Goal**: RevOps analysts can view a web dashboard showing recommendation feeds, decision trails, acceptance rate analytics, confidence distributions, and low-confidence classifications for review.

**Independent Test**: Log into the dashboard, view the recommendations feed with filters (status, confidence, date range). Click a recommendation to see its decision trail. View the analytics page with approval rates and latency metrics.

**Dependency**: Requires US1 models (recommendations, classifications exist in DB). Backend API routes can start after Foundational. Dashboard setup can start after US1. Bulk approve/reject in dashboard extends US2 approval flow.

### Backend API Routes for User Story 3

- [x] T058 [US3] Implement recommendation list (paginated, filterable by status/deal/confidence/date, sortable), get single, and decision trail endpoints in backend/app/api/routes/recommendations.py
- [x] T059 [US3] Add bulk approve/reject endpoint (RevOps/admin only, batch process with per-item error reporting) to backend/app/api/routes/recommendations.py
- [x] T060 [P] [US3] Implement deal list (paginated, filterable by pipeline/owner/has_threads) and get detail endpoints in backend/app/api/routes/deals.py
- [x] T061 [P] [US3] Implement analytics overview endpoint (approval/rejection/expiration rates, confidence percentiles, latency p50/p95, deal coverage) and low-confidence classifications endpoint in backend/app/api/routes/analytics.py
- [x] T062 [P] [US3] Implement audit trail query endpoint (by entity_type + entity_id, paginated) in backend/app/api/routes/audit.py
- [x] T063 [US3] Register US3 routes (deals, analytics, audit; extend recommendations) in backend/app/main.py

### Dashboard Foundation for User Story 3

- [x] T064 [US3] Setup Next.js dashboard: root layout with Tailwind, auth pages (login redirect, OIDC callback), and protected dashboard layout in dashboard/src/app/
- [x] T065 [P] [US3] Define shared TypeScript types matching API schemas (Recommendation, Deal, DecisionTrail, AnalyticsOverview, UserConfig, PipelineConfig, etc.) in dashboard/src/types/index.ts
- [x] T066 [P] [US3] Implement typed API client with auth token handling, error mapping, and pagination support in dashboard/src/lib/api-client.ts
- [x] T067 [P] [US3] Implement OIDC session management (token storage, refresh, redirect on expiry) in dashboard/src/lib/auth.ts

### Dashboard Pages for User Story 3

- [x] T068 [US3] Implement recommendations list page (sortable table, status/confidence/date filters, bulk select with approve/reject actions) in dashboard/src/app/dashboard/recommendations/page.tsx
- [x] T069 [US3] Implement decision trail detail page (email excerpt -> classification -> mapping -> user action -> CRM result chain view) in dashboard/src/app/dashboard/recommendations/[id]/page.tsx
- [x] T070 [US3] Implement analytics/KPI dashboard page (approval rate chart, rejection reasons breakdown, confidence distribution, latency gauges, deal coverage metric) in dashboard/src/app/dashboard/analytics/page.tsx
- [x] T071 [US3] Implement deals overview page (deal list with pipeline, stage, owner, thread count, recommendation count) in dashboard/src/app/dashboard/deals/page.tsx

**Checkpoint**: Dashboard operational -- RevOps can monitor pipeline intelligence, review decision trails, view analytics, and bulk-manage recommendations.

---

## Phase 6: User Story 4 -- System Administration & Configuration (Priority: P4)

**Goal**: Admins can manage users, configure pipeline-to-stage mappings, adjust confidence thresholds, manage prompt versions, and monitor system health.

**Independent Test**: Log into the admin panel, add a new user with email/CRM/Slack linking, configure a pipeline's intent-to-stage mapping, change the confidence threshold, edit the classification prompt, and verify all changes take effect immediately with audit log entries.

**Dependency**: Backend API routes can start after Foundational. Dashboard admin pages depend on US3 dashboard foundation.

### Backend API Routes for User Story 4

- [x] T072 [US4] Implement user management CRUD routes (GET list, POST create with role/hubspot/slack mapping, PATCH update, DELETE soft-deactivate) in backend/app/api/routes/admin.py
- [x] T073 [US4] Add pipeline config routes (GET list, GET single, PATCH update intent_to_stage_rules/thresholds/timeout/max_snoozes with audit log) to backend/app/api/routes/admin.py
- [x] T074 [US4] Add prompt version management routes (GET list, POST create new version, POST activate with auto-deactivate previous, POST rollback) to backend/app/api/routes/admin.py

### Workers for User Story 4

- [x] T075 [P] [US4] Implement HubSpot pipeline metadata sync worker (periodic fetch of pipelines/stages, upsert PipelineConfig, detect stage changes) in backend/app/workers/pipeline_sync.py
- [x] T076 [P] [US4] Implement OAuth token proactive refresh worker (query credentials approaching expiry, refresh tokens, re-encrypt, alert on failure) in backend/app/workers/token_refresher.py
- [x] T077 [P] [US4] Implement DLQ processor worker (retry failed messages from Redis DLQ with backoff, overflow to dead_messages table after max retries, Slack alert) in backend/app/workers/dlq_processor.py

### Route Registration for User Story 4

- [x] T078 [US4] Register US4 admin routes in backend/app/main.py

### Dashboard Admin Pages for User Story 4

- [x] T079 [US4] Implement admin users management page (user table, add/edit/deactivate forms, role assignment, external account linking) in dashboard/src/app/dashboard/admin/users/page.tsx
- [x] T080 [P] [US4] Implement admin pipelines configuration page (pipeline list, stage editor, intent-to-stage mapping editor, threshold sliders) in dashboard/src/app/dashboard/admin/pipelines/page.tsx
- [x] T081 [P] [US4] Implement admin prompts management page (version list, create new version form, activate/rollback controls, diff view) in dashboard/src/app/dashboard/admin/prompts/page.tsx
- [x] T082 [P] [US4] Implement admin thresholds configuration page (recommendation threshold, logging threshold, approval timeout, max snoozes per pipeline) in dashboard/src/app/dashboard/admin/thresholds/page.tsx
- [x] T083 [US4] Implement admin system health monitoring page (real-time integration status for Gmail/HubSpot/LLM/Slack, operational metrics, DLQ depth) in dashboard/src/app/dashboard/admin/health/page.tsx

**Checkpoint**: Full admin capability -- users, pipelines, prompts, and system health all configurable through the web dashboard.

---

## Phase 7: Polish & Cross-Cutting Concerns

**Purpose**: Production readiness, containerization, and end-to-end validation

- [x] T084 [P] Implement Prometheus metrics collection (email processing latency, classification latency, recommendation counts by status, API request duration) and /metrics endpoint in backend/app/api/routes/health.py
- [x] T085 [P] Create backend multi-stage Dockerfile (Python 3.11-slim, pip install, non-root user, health check) in backend/Dockerfile
- [x] T086 [P] Create dashboard multi-stage Dockerfile (Node 20-alpine, npm build, standalone output) in dashboard/Dockerfile
- [x] T087 Update docker-compose.yml with all services (backend, dashboard, workers, postgres, redis) and health checks in infra/docker-compose.yml
- [x] T088 Validate end-to-end pipeline flow per quickstart.md test scenarios (email send -> Pub/Sub -> classify -> recommend -> Slack -> approve -> CRM update)
- [x] T089 Final route registration audit and dependency wiring verification across backend/app/main.py and backend/app/dependencies.py

---

## Dependencies & Execution Order

### Phase Dependencies

- **Setup (Phase 1)**: No dependencies -- can start immediately
- **Foundational (Phase 2)**: Depends on Setup (T001) -- **BLOCKS all user stories**
- **US1 (Phase 3)**: Depends on Foundational completion -- core pipeline
- **US2 (Phase 4)**: Depends on US1 completion (needs recommendation models, notification service, Slack client)
- **US3 (Phase 5)**: Backend API routes depend on US1 models. Dashboard depends on US1 for meaningful data. Bulk actions extend US2.
- **US4 (Phase 6)**: Backend admin routes depend on Foundational only (user_configs, pipeline_configs, prompt_versions). Dashboard admin pages depend on US3 dashboard foundation (T064-T067).
- **Polish (Phase 7)**: Depends on all user stories being complete

### User Story Dependencies

- **US1 (P1)**: Can start after Foundational (Phase 2) -- No dependencies on other stories
- **US2 (P2)**: Depends on US1 -- needs StageRecommendation model, Slack client, notification service
- **US3 (P3)**: Backend routes can start after US1 models exist. Dashboard foundation can start after US1. Full testing requires US1+US2 data.
- **US4 (P4)**: Backend admin routes can start after Foundational (parallel with US1). Dashboard admin pages require US3 dashboard foundation (T064-T067). Workers (T075-T077) can start after Foundational.

### Within Each User Story

- Models before services (ORM layer must exist for persistence)
- Integration clients before services that use them
- Services before API routes (routes call services)
- Backend routes before dashboard pages (dashboard calls API)
- Core implementation before convenience features (bulk actions after single actions)

### Parallel Opportunities

**Phase 1** (after T001):
- T002, T003, T004, T005 -- all independent setup files

**Phase 2** (after T006):
- T007-T012 -- base model and all utility modules (different files)
- T013-T019 -- all ORM models (different files, depend on T007)
- T021-T023, T026 -- protocols, middleware, health route (different files)

**Phase 3 / US1** (after T034 migration):
- T035-T038, T040 -- all integration clients (different provider directories)
- T030-T033 -- all US1 models (different files)

**Phase 5 / US3**:
- T060, T061, T062 -- deals, analytics, audit routes (different files)
- T065, T066, T067 -- types, API client, auth lib (different files)

**Phase 6 / US4**:
- T075, T076, T077 -- all workers (different files)
- T080, T081, T082 -- pipeline, prompt, threshold admin pages (different files)

---

## Parallel Example: User Story 1

```bash
# After T034 (migration), launch all integration clients in parallel:
Task: "T035 [P] [US1] Implement Gmail API client in backend/app/integrations/gmail/client.py"
Task: "T036 [P] [US1] Implement HubSpot API client in backend/app/integrations/hubspot/client.py"
Task: "T037 [P] [US1] Implement Anthropic Claude client in backend/app/integrations/llm/anthropic.py"
Task: "T038 [P] [US1] Implement OpenAI GPT fallback client in backend/app/integrations/llm/openai.py"
Task: "T040 [P] [US1] Implement Slack API client in backend/app/integrations/slack/client.py"

# Then sequentially build the service chain:
Task: "T041 [US1] PII redactor"
Task: "T042 [US1] Email ingestion service"
Task: "T043 [US1] Thread linker service"
Task: "T044 [US1] Intent analyzer service"
Task: "T045 [US1] Stage mapper service"
Task: "T046 [US1] Recommendation generation service"
Task: "T047 [US1] Notification service"
```

---

## Parallel Example: User Story 3

```bash
# Backend API routes (different files) in parallel:
Task: "T060 [P] [US3] Deal endpoints in backend/app/api/routes/deals.py"
Task: "T061 [P] [US3] Analytics endpoints in backend/app/api/routes/analytics.py"
Task: "T062 [P] [US3] Audit trail endpoint in backend/app/api/routes/audit.py"

# Dashboard libraries (different files) in parallel:
Task: "T065 [P] [US3] TypeScript types in dashboard/src/types/index.ts"
Task: "T066 [P] [US3] API client in dashboard/src/lib/api-client.ts"
Task: "T067 [P] [US3] Auth session in dashboard/src/lib/auth.ts"
```

---

## Implementation Strategy

### MVP First (User Story 1 Only)

1. Complete Phase 1: Setup
2. Complete Phase 2: Foundational (CRITICAL -- blocks all stories)
3. Complete Phase 3: User Story 1
4. **STOP and VALIDATE**: Send test email, verify Slack recommendation arrives within 2 minutes
5. Deploy/demo the core detection pipeline

### Incremental Delivery

1. Setup + Foundational -> Infrastructure ready
2. **US1** -> Email detection + Slack recommendations (MVP!)
3. **US2** -> Approval workflow + CRM writeback (closes the loop)
4. **US3** -> Dashboard + analytics (RevOps visibility)
5. **US4** -> Admin panel + config management (operational control)
6. Each story adds value without breaking previous stories

### Parallel Team Strategy

With multiple developers after Foundational phase:

1. **Team completes Setup + Foundational together**
2. Once Foundational is done:
   - Developer A: US1 (core pipeline -- must complete first)
   - Developer B: US4 backend admin routes + workers (only needs Foundational models)
3. After US1 completes:
   - Developer A: US2 (approval workflow)
   - Developer B: US3 backend API routes
4. After US2 + US3 backend:
   - Developer A: US3 dashboard pages
   - Developer B: US4 dashboard admin pages

---

## Notes

- [P] tasks = different files, no dependencies on incomplete tasks in the same group
- [Story] label maps each task to its specific user story for traceability
- No test tasks generated (not explicitly requested in spec)
- `backend/app/api/routes/analytics.py` is a new route file not in the original plan.md structure, required for /analytics/* endpoints defined in api.yaml
- Services are chained sequentially in US1 because each feeds into the next: ingest -> link -> classify -> map -> recommend -> notify
- The recommendation routes file (recommendations.py) is built incrementally: US2 adds action endpoints, US3 adds list/query/trail endpoints
- HubSpot client (hubspot/client.py) is built incrementally: US1 adds read operations, US2 adds write operations
- Commit after each task or logical group of parallel tasks
- Stop at any checkpoint to validate the story independently
