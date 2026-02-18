<!--
  Sync Impact Report
  ==================
  Version change: N/A (initial) -> 1.0.0
  Modified principles: N/A (all new)
  Added sections:
    - Core Principles (7 principles)
    - Technology Stack & Constraints
    - Development Workflow & Quality Gates
    - Governance
  Removed sections: N/A
  Templates requiring updates:
    - .specify/templates/plan-template.md: ✅ No update needed (Constitution Check section is dynamic)
    - .specify/templates/spec-template.md: ✅ No update needed (template structure compatible)
    - .specify/templates/tasks-template.md: ✅ No update needed (phase structure accommodates principles)
  Follow-up TODOs: None
-->

# HubSpot Pipeline Intelligence Constitution

## Core Principles

### I. Human-in-the-Loop (NON-NEGOTIABLE)

Every CRM stage change MUST be explicitly approved by a human before
being written to HubSpot. The system MUST NOT auto-approve, auto-write,
or bypass human review under any circumstance, regardless of confidence
score. This is the foundational trust contract with sales users.

- All recommendations MUST present [Approve], [Reject], and [Snooze]
  actions to the deal owner.
- No code path may write to HubSpot deal stages without a recorded
  human approval event in the audit log.
- Unanswered recommendations MUST expire (default: 48 hours) rather
  than auto-approve.
- Rejection feedback MUST be captured and fed back as a training signal.

### II. Data Privacy & Minimization

The system MUST minimize data retention and protect personally
identifiable information. Email bodies are transient and MUST NOT be
persisted after classification.

- Full email bodies MUST NOT be stored in the database. Only metadata
  and a 500-character excerpt are retained post-classification.
- PII (phone numbers, SSN, credit card numbers) MUST be redacted before
  transmission to any LLM provider.
- Data retention policies MUST be enforced: recommendations 12 months,
  audit logs 24 months, email metadata 6 months, LLM logs 30 days.
- GDPR right-to-deletion MUST be supported: purge all records for a
  contact within 30 days of request.
- LLM providers MUST be configured for zero data retention (no training
  on customer data).

### III. Auditability & Explainability

Every decision the system makes MUST be traceable from the triggering
email through classification, recommendation, human action, and CRM
write. No silent actions.

- Every state transition MUST be recorded in an immutable audit log
  (INSERT and SELECT only; no UPDATE or DELETE).
- Every recommendation MUST include: intent detected, key phrases,
  confidence score with qualitative label, and the mapping rule applied.
- A "Decision Trail" view MUST reconstruct the full chain: email ->
  classification -> mapping -> recommendation -> user action -> CRM
  result.
- Each classification MUST record the prompt version and LLM model used.

### IV. Resilience & Zero Data Loss

No email MUST be silently dropped. The system MUST guarantee at-least-once
processing with idempotency to handle duplicates.

- Pub/Sub messages MUST be acknowledged only after successful
  persistence of email metadata.
- All external API calls MUST use exponential backoff with jitter on
  failure.
- Circuit breakers MUST protect against cascading failures from external
  dependencies (Gmail, HubSpot, LLM, Slack).
- Failed messages MUST be routed to a Dead Letter Queue. DLQ overflow
  MUST persist to PostgreSQL.
- Messages in DLQ MUST be retried automatically (every 15 minutes,
  max 10 retries) before requiring manual intervention.

### V. Security by Default

All credentials, tokens, and sensitive data MUST be protected using
industry-standard encryption and access controls.

- OAuth tokens (Gmail, HubSpot, Slack) MUST be AES-256 encrypted at
  rest in a dedicated credentials table.
- All external API calls MUST use HTTPS with TLS 1.2 or higher.
- Token refresh MUST happen proactively before expiration (Gmail at
  45 min, HubSpot at 5 hours).
- RBAC MUST be enforced at the API layer: admin (full access), revops
  (pipeline config + analytics + batch review), sales_user (own
  recommendations only).
- Slack interaction webhooks MUST validate X-Slack-Signature on every
  request.
- Secrets MUST be stored in a secrets manager (GCP Secret Manager) in
  production; `.env` files for local development only.

### VI. Modular Architecture

The system MUST be composed of distinct, loosely coupled modules with
well-defined interfaces. Single process for pilot; extractable to
independent services later.

- Components (ingestion, classification, recommendation, notification,
  CRM update) MUST communicate through defined interfaces, not direct
  internal coupling.
- All external integrations (Gmail, HubSpot, Slack, LLM) MUST be
  abstracted behind Python ABCs or Protocols to enable provider
  swapping.
- Configuration MUST follow the hierarchy: environment variables
  (infrastructure) -> database config (runtime) -> hardcoded defaults.
- Database migrations MUST use Alembic with forward-only in production.

### VII. Observability

The system MUST produce structured, traceable telemetry sufficient to
diagnose any failure or latency issue end-to-end.

- All logs MUST be structured JSON with: timestamp, level, service,
  trace_id, span_id, user_id, message, metadata.
- Every processing step MUST carry a trace_id (UUID assigned at Pub/Sub
  receipt) for end-to-end correlation.
- Prometheus-compatible metrics MUST be emitted for: email throughput,
  classification counts, recommendation lifecycle, CRM write outcomes,
  LLM latency, and DLQ depth.
- Alerts MUST fire (via Slack webhook) for: DLQ depth > 50, LLM error
  rate > 10%/5min, HubSpot error rate > 5%/5min, watch renewal failure,
  no emails processed for an active user in 24 hours.

## Technology Stack & Constraints

- **Backend**: Python 3.11+, FastAPI, SQLAlchemy ORM, Alembic
  migrations, APScheduler for background jobs.
- **Frontend**: Next.js 14, TypeScript, Tailwind CSS.
- **Database**: PostgreSQL 15+ (primary storage), Redis 7+ (caching,
  rate limiting, DLQ).
- **LLM**: Primary: Anthropic Claude Haiku 4.5; Fallback: OpenAI
  GPT-4o-mini. Token budget: 4,096 input / 512 output per
  classification.
- **Cloud**: GCP (Pub/Sub, Cloud Run, Cloud SQL, Memorystore, Secret
  Manager).
- **Integrations**: Gmail API (push via Pub/Sub), HubSpot API v3,
  Slack API (Block Kit + interactions).
- **Pilot Scope**: 10-20 users, ~1,000 emails/day, single Cloud Run
  instance. Design MUST NOT preclude horizontal scaling to 500+ users.
- **Latency Targets**: Email-to-notification p50 < 60s, p95 < 120s.
  Approval-to-CRM-write p50 < 3s, p95 < 10s.
- **Availability**: 99.5% uptime target (~3.6 hours/month max
  downtime).

## Development Workflow & Quality Gates

- **Test Coverage**: Unit tests MUST achieve > 80% coverage on business
  logic. Integration tests MUST mock all external APIs (Gmail, HubSpot,
  Claude, Slack). E2E tests MUST use a HubSpot sandbox account.
- **Code Quality**: All code MUST pass linting and formatting checks
  before merge.
- **Prompt Versioning**: LLM prompts MUST be versioned in the database
  (not hardcoded). Every classification MUST record the prompt version
  used. Prompt changes MUST be auditable with before/after state.
- **Configuration Changes**: All runtime configuration changes (pipeline
  mappings, thresholds, user management) MUST be audit-logged with
  before/after state and actor identity.
- **Deployment**: Containerized via Docker. Infrastructure managed via
  Terraform. CI/CD via GitHub Actions.
- **Branching**: Feature branches off main. PRs require review before
  merge.

## Governance

This constitution is the authoritative source of non-negotiable
engineering principles for the HubSpot Pipeline Intelligence project.
It supersedes ad-hoc decisions and informal agreements.

- **Compliance**: Every PR and code review MUST verify adherence to
  these principles. Violations MUST be resolved before merge.
- **Amendments**: Any change to this constitution MUST be documented
  with rationale, reviewed by at least one team member, and accompanied
  by a migration plan if existing code is affected.
- **Versioning**: This document follows semantic versioning. MAJOR:
  principle removal or redefinition. MINOR: new principle or material
  expansion. PATCH: clarifications and wording fixes.
- **Review Cadence**: Constitution MUST be reviewed at pilot midpoint
  (Week 6) and end (Week 12) against actual system behavior and
  feedback.
- **Guidance**: Use the PRD
  (`Hubspot_Pipeline_intelligence_PRD_v1.md`) as the authoritative
  source for detailed functional and non-functional requirements.

**Version**: 1.0.0 | **Ratified**: 2026-02-15 | **Last Amended**: 2026-02-15
