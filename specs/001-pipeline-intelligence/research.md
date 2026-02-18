# Research: HubSpot Pipeline Intelligence

**Date**: 2026-02-15
**Status**: Complete (all decisions resolved from PRD)

## R1: Email Monitoring Approach

**Decision**: Gmail API push notifications via Google Cloud Pub/Sub (users.watch)

**Rationale**: Push-based monitoring provides near-real-time notification
(< 2s delivery) without polling overhead. Gmail's users.watch API
publishes historyId changes to a Pub/Sub topic, enabling efficient
incremental sync via history.list. The pull subscription model allows
debuggability during pilot.

**Alternatives considered**:
- **Gmail API polling (users.messages.list)**: Simpler but introduces
  latency (polling interval) and wastes quota on empty checks. At 10-20
  users, ~500-1,000 emails/day, polling every 30s = ~57,600 API calls/day
  vs ~1,000 Pub/Sub messages. Rejected for efficiency.
- **IMAP IDLE**: Lower-level, requires persistent connections per user,
  no native GCP integration, harder to scale. Rejected for operational
  complexity.
- **Gmail API push with HTTP endpoint**: Pub/Sub push to a Cloud Run
  endpoint. Viable but pull subscription chosen for pilot debuggability
  (message inspection, replay).

---

## R2: LLM Provider Selection

**Decision**: Primary: Anthropic Claude Haiku 4.5 (~$0.0025/classification).
Fallback: OpenAI GPT-4o-mini.

**Rationale**: Claude Haiku 4.5 offers the best cost/quality ratio for
structured classification tasks. At ~1,000 emails/day, monthly cost is
~$75. The model achieves 85%+ accuracy on well-scoped intent
classification with structured JSON output. Fallback to GPT-4o-mini
provides resilience against single-provider outages.

**Alternatives considered**:
- **Claude Sonnet 4.5**: Higher quality but ~10x cost (~$750/month).
  Overkill for intent classification where Haiku performs adequately.
  Rejected for cost.
- **GPT-4o-mini only**: Comparable quality and cost but no provider
  redundancy. Using as fallback instead of primary.
- **Open-source models (Llama, Mistral)**: Requires self-hosting,
  GPU infrastructure, and maintenance. Cost savings don't justify
  operational complexity at pilot scale. Rejected.
- **Fine-tuned classifier**: Would require labeled training data that
  doesn't exist yet. Phase 1 generates this data via approval/rejection
  feedback. Fine-tuning is a Phase 2+ optimization.

---

## R3: CRM Integration Pattern

**Decision**: HubSpot API v3 with private app token (pilot), Redis-backed
token bucket rate limiter (110 req/10s for OAuth, 190 req/10s for
private apps).

**Rationale**: Private app tokens provide a simpler auth model (no OAuth
refresh dance) and higher rate limits (190 vs 110 req/10s) for single-org
pilot. Read-before-write pattern prevents silent conflict overwrites.
Deal notes provide audit trail visibility within HubSpot itself.

**Alternatives considered**:
- **HubSpot OAuth public app**: Required for multi-tenant SaaS. More
  complex (token refresh, per-user tokens). Acceptable for Phase 3
  multi-tenant, not needed for single-org pilot.
- **HubSpot webhooks (bidirectional sync)**: Would provide real-time
  deal change detection. Out of scope for Phase 1; planned for Phase 3.
- **Direct database access**: Not possible with HubSpot (SaaS). N/A.

---

## R4: Notification & Approval Channel

**Decision**: Slack Block Kit interactive messages (primary), Next.js web
dashboard (secondary/RevOps).

**Rationale**: Sales reps live in Slack. Block Kit interactive messages
allow approve/reject/snooze with a single tap without context-switching.
Slack interaction payloads provide a webhook-based callback model that
integrates cleanly with the FastAPI backend. Web dashboard serves
RevOps for bulk operations, analytics, and as a Slack fallback.

**Alternatives considered**:
- **Email notifications**: Lower engagement rate, no inline action
  buttons (requires link-click to web app). Rejected for adoption risk.
- **Microsoft Teams**: Not used by the pilot organization. Could be
  added via the MessagingProvider abstraction layer in Phase 3.
- **Web-only**: Requires reps to visit a dashboard, breaking their
  workflow. Rejected for adoption risk (Slack Adoption Dependency is
  Risk R10 in the PRD, mitigated by web dashboard fallback).

---

## R5: Queue & Retry Strategy

**Decision**: GCP Pub/Sub for email notifications (at-least-once
delivery), Redis lists for Dead Letter Queue, PostgreSQL dead_messages
table for DLQ overflow (retry_count > 10).

**Rationale**: Pub/Sub guarantees at-least-once delivery and handles
Gmail's push notification protocol natively. Redis DLQ provides fast
read/write for transient failures. PostgreSQL overflow ensures no
message is ever truly lost, even during extended outages. Exponential
backoff with jitter (base * 2^attempt + random(0,1s), capped at max)
prevents thundering herd.

**Alternatives considered**:
- **RabbitMQ / Kafka**: Full message brokers are overkill for pilot
  scale (~42 messages/hour average). Adds operational complexity.
  Redis lists + Pub/Sub are sufficient.
- **Cloud Tasks**: GCP-native task queue. Viable but adds another GCP
  dependency. Redis DLQ is simpler and already needed for caching.
- **Database-only queue**: PostgreSQL as queue (SELECT FOR UPDATE SKIP
  LOCKED). Works but slower than Redis for high-frequency operations.
  Reserved for overflow only.

---

## R6: Authentication & Authorization

**Decision**: Google Workspace OIDC (SSO) for web dashboard. Slack
OAuth for bot installation. RBAC enforced at FastAPI middleware layer
with three roles: admin, revops, sales_user.

**Rationale**: The pilot organization uses Google Workspace. OIDC
provides SSO with no additional credential management. RBAC is
straightforward with three roles matching the three personas (David/admin,
Marcus/revops, Sarah/sales_user). API-layer enforcement ensures
consistent access control regardless of client (dashboard or direct API).

**Alternatives considered**:
- **JWT-based custom auth**: Requires building auth infrastructure.
  Unnecessary when OIDC is available.
- **API keys**: Too coarse for role-based access. No user identity.
- **Auth0 / Clerk**: Third-party auth services. Adds cost and another
  dependency for a 10-20 user pilot. Overkill.

---

## R7: Data Storage Architecture

**Decision**: PostgreSQL 15+ (primary persistent storage), Redis 7+
(caching, rate limiting, DLQ, session data).

**Rationale**: PostgreSQL provides ACID transactions for the
recommendation state machine, JSONB for flexible metadata (audit logs,
pipeline configs), array types for multi-value fields (to_addresses,
key_phrases), and mature tooling (Alembic migrations, pg_dump). Redis
provides sub-millisecond reads for contact resolution cache (1-hour TTL),
token bucket rate limiting, and fast DLQ operations.

**Alternatives considered**:
- **MySQL**: Lacks native array types and JSONB. PostgreSQL is a better
  fit for the polymorphic audit log and array-heavy schema.
- **MongoDB**: Document store adds operational complexity without benefit.
  The data model is relational (email -> thread -> deal -> recommendation).
- **DynamoDB**: Locked to AWS. The project targets GCP (Cloud SQL).

---

## R8: PII Redaction Strategy

**Decision**: Regex-based PII detection and replacement before LLM
transmission. Redact: phone numbers -> [PHONE], SSN/CC patterns ->
[REDACTED], email signatures stripped. Retain: email addresses and
names (required for contact resolution).

**Rationale**: Regex patterns are sufficient for structured PII formats
(phone numbers, SSN, credit card numbers) and run with negligible
latency (< 1ms). Email signatures are stripped to reduce token usage
and remove irrelevant PII (personal phone, address). Names and email
addresses must be retained for the LLM to understand sender/recipient
context.

**Alternatives considered**:
- **NER-based redaction (spaCy, Presidio)**: Higher accuracy for
  unstructured PII but adds ~100ms latency and a heavy dependency.
  Overkill for the structured patterns we need to catch.
- **LLM-based redaction**: Circular dependency (sending PII to redact
  PII). Rejected.
- **No redaction**: Violates Constitution Principle II. Rejected.

---

## R9: Circuit Breaker Configuration

**Decision**: Per-integration circuit breakers with the following
configuration:
- Gmail: Open after 5 consecutive failures, half-open after 60s
- HubSpot: Open after 5 consecutive failures, half-open after 60s
- LLM: Open after 3 consecutive failures, half-open after 30s
- Slack: Open after 5 consecutive failures, half-open after 60s

**Rationale**: LLM has a lower threshold (3) because classification is
the most latency-sensitive step and has a secondary provider fallback.
Other integrations use 5 failures to tolerate transient network issues.
Half-open timers (30-60s) balance recovery speed against overwhelming
a recovering service.

**Alternatives considered**:
- **No circuit breakers (retry only)**: Risks cascading failures when
  an external service is down. Rejected per Constitution Principle IV.
- **Global circuit breaker**: Too coarse. A HubSpot outage should not
  stop email ingestion.
- **Sliding window (error rate %)**: More sophisticated but unnecessary
  at pilot scale with low throughput (~42/hour).

---

## R10: Observability Stack

**Decision**: Structured JSON logging (Python logging + structlog),
prometheus-client for metrics, Slack webhooks for alerting.

**Rationale**: structlog produces machine-parseable JSON logs that
integrate with any log aggregator (Cloud Logging for pilot).
prometheus-client is the de facto standard for metrics and integrates
with Cloud Monitoring or self-hosted Grafana. Slack alerting leverages
the team's existing communication channel with no additional
infrastructure.

**Alternatives considered**:
- **OpenTelemetry**: Full tracing framework. Valuable but adds
  significant setup for pilot. Can be adopted incrementally in Phase 2.
  trace_id propagation (manual UUID) achieves basic correlation now.
- **Datadog / New Relic**: Paid observability platforms. Overkill for
  10-20 user pilot. GCP Cloud Logging + Monitoring is sufficient.
- **ELK stack**: Self-hosted. Operational burden not justified for
  pilot.
