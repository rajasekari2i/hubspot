# Data Model: HubSpot Pipeline Intelligence

**Date**: 2026-02-15
**Source**: spec.md Key Entities + PRD Section 9

## Entity Overview

```text
user_configs 1───* email_messages       (user owns emails)
user_configs 1───* credentials          (per provider)
user_configs 1───* deals                (as HubSpot owner)
email_messages *───1 email_threads      (many emails per thread)
email_threads  *───1 deals              (many threads per deal)
deals *───1 pipeline_configs            (deal belongs to pipeline)
stage_recommendations *───1 email_messages  (triggered by email)
stage_recommendations *───1 email_threads   (within thread)
stage_recommendations *───1 deals           (for deal)
intent_classifications *───1 email_messages (one per email)
audit_logs: polymorphic via entity_type + entity_id (no FK)
```

---

## Entities

### user_configs

System user profiles with linked external accounts.

| Field | Type | Constraints | Description |
|-------|------|-------------|-------------|
| id | UUID | PK, default gen | Internal identifier |
| email | VARCHAR(255) | UNIQUE, NOT NULL | User email (login identity) |
| display_name | VARCHAR(255) | NOT NULL | Display name |
| role | ENUM | NOT NULL, values: admin/revops/sales_user | RBAC role |
| hubspot_user_id | VARCHAR(50) | NULLABLE | HubSpot user ID |
| hubspot_owner_id | VARCHAR(50) | NULLABLE | HubSpot owner ID for deal ownership |
| slack_user_id | VARCHAR(50) | NULLABLE | Slack user ID for notifications |
| gmail_watch_expiration | TIMESTAMPTZ | NULLABLE | When Gmail watch expires |
| gmail_last_history_id | BIGINT | NULLABLE | Last processed Gmail history ID |
| notification_channel | VARCHAR(20) | DEFAULT 'slack' | Preferred notification channel |
| is_active | BOOLEAN | DEFAULT true | Whether user is active |
| created_at | TIMESTAMPTZ | DEFAULT now() | Record creation |
| updated_at | TIMESTAMPTZ | DEFAULT now() | Last modification |

**Indexes**: UNIQUE(email), INDEX(hubspot_owner_id), INDEX(is_active)

---

### credentials

Encrypted OAuth tokens for external services.

| Field | Type | Constraints | Description |
|-------|------|-------------|-------------|
| id | UUID | PK | Internal identifier |
| user_id | UUID | FK -> user_configs.id, NOT NULL | Owning user |
| provider | ENUM | NOT NULL, values: gmail/hubspot/slack | Service provider |
| access_token_enc | BYTEA | NOT NULL | AES-256 encrypted access token |
| refresh_token_enc | BYTEA | NULLABLE | AES-256 encrypted refresh token |
| token_expiry | TIMESTAMPTZ | NOT NULL | When access token expires |
| scopes | TEXT[] | NOT NULL | Granted OAuth scopes |
| created_at | TIMESTAMPTZ | DEFAULT now() | |
| updated_at | TIMESTAMPTZ | DEFAULT now() | |

**Constraints**: UNIQUE(user_id, provider)
**Indexes**: INDEX(user_id), INDEX(token_expiry) for proactive refresh queries

---

### email_messages

Gmail message metadata (no full body stored per Constitution Principle II).

| Field | Type | Constraints | Description |
|-------|------|-------------|-------------|
| id | UUID | PK | Internal identifier |
| gmail_message_id | VARCHAR(50) | UNIQUE, NOT NULL | Gmail message ID |
| gmail_thread_id | VARCHAR(50) | NOT NULL | Gmail thread ID |
| gmail_history_id | BIGINT | NOT NULL | Gmail history ID for dedup |
| user_id | UUID | FK -> user_configs.id, NOT NULL | Monitored user |
| from_address | VARCHAR(255) | NOT NULL | Sender email |
| to_addresses | TEXT[] | NOT NULL | Recipient emails |
| cc_addresses | TEXT[] | DEFAULT '{}' | CC emails |
| subject | VARCHAR(500) | NOT NULL | Email subject line |
| body_excerpt | VARCHAR(500) | NULLABLE | 500-char excerpt (post-classification only) |
| received_at | TIMESTAMPTZ | NOT NULL | When email was received |
| processed_at | TIMESTAMPTZ | NULLABLE | When processing completed |
| processing_status | ENUM | NOT NULL, DEFAULT 'pending' | See state machine below |
| trace_id | UUID | NOT NULL | End-to-end trace identifier |
| created_at | TIMESTAMPTZ | DEFAULT now() | |

**Processing Status States**: pending -> processing -> classified -> failed
**Indexes**: UNIQUE(gmail_message_id), INDEX(gmail_thread_id), INDEX(user_id, received_at), INDEX(processing_status), INDEX(trace_id)
**Retention**: 6 months, then DELETE

---

### email_threads

Gmail thread -> HubSpot deal mapping. Once linked, subsequent emails
reuse the linkage without re-resolving.

| Field | Type | Constraints | Description |
|-------|------|-------------|-------------|
| id | UUID | PK | Internal identifier |
| gmail_thread_id | VARCHAR(50) | UNIQUE, NOT NULL | Gmail thread ID |
| deal_id | UUID | FK -> deals.id, NULLABLE | Linked HubSpot deal |
| contact_ids | UUID[] | DEFAULT '{}' | Resolved HubSpot contact IDs |
| subject | VARCHAR(500) | NULLABLE | Thread subject |
| message_count | INTEGER | DEFAULT 0 | Number of messages in thread |
| last_activity_at | TIMESTAMPTZ | NULLABLE | Last email timestamp |
| link_confidence | DECIMAL(4,3) | NULLABLE | Confidence of deal linkage |
| link_method | VARCHAR(50) | NULLABLE | How linked: email_match/subject_fuzzy/manual |
| created_at | TIMESTAMPTZ | DEFAULT now() | |
| updated_at | TIMESTAMPTZ | DEFAULT now() | |

**Indexes**: UNIQUE(gmail_thread_id), INDEX(deal_id)

---

### deals

Cached HubSpot deal data. Periodically synced from HubSpot.

| Field | Type | Constraints | Description |
|-------|------|-------------|-------------|
| id | UUID | PK | Internal identifier |
| hubspot_deal_id | VARCHAR(50) | UNIQUE, NOT NULL | HubSpot deal ID |
| pipeline_id | UUID | FK -> pipeline_configs.id, NULLABLE | Pipeline config |
| hubspot_pipeline_id | VARCHAR(50) | NOT NULL | HubSpot pipeline ID |
| current_stage | VARCHAR(50) | NOT NULL | Current HubSpot stage ID |
| current_stage_name | VARCHAR(255) | NOT NULL | Human-readable stage name |
| deal_name | VARCHAR(500) | NOT NULL | Deal name |
| owner_user_id | UUID | FK -> user_configs.id, NULLABLE | Deal owner in our system |
| contact_ids | UUID[] | DEFAULT '{}' | Associated contact IDs |
| amount | DECIMAL(15,2) | NULLABLE | Deal amount |
| close_date | DATE | NULLABLE | Expected close date |
| last_synced_at | TIMESTAMPTZ | NOT NULL | Last HubSpot sync time |
| created_at | TIMESTAMPTZ | DEFAULT now() | |
| updated_at | TIMESTAMPTZ | DEFAULT now() | |

**Indexes**: UNIQUE(hubspot_deal_id), INDEX(owner_user_id), INDEX(hubspot_pipeline_id), INDEX(current_stage)

---

### intent_classifications

All LLM classifications (including below-threshold). Used for analytics
and training data collection.

| Field | Type | Constraints | Description |
|-------|------|-------------|-------------|
| id | UUID | PK | Internal identifier |
| email_message_id | UUID | FK -> email_messages.id, NOT NULL | Classified email |
| deal_id | UUID | FK -> deals.id, NULLABLE | Associated deal |
| intent | VARCHAR(50) | NOT NULL | Classified intent category |
| confidence_score | DECIMAL(4,3) | NOT NULL, CHECK 0.000-1.000 | Model confidence |
| reasoning | TEXT | NOT NULL | Model's reasoning text |
| key_phrases | TEXT[] | DEFAULT '{}' | Extracted key phrases |
| direction | ENUM | NOT NULL, values: forward/backward/neutral | Stage direction |
| prompt_version | VARCHAR(20) | NOT NULL | Prompt version used |
| llm_model | VARCHAR(50) | NOT NULL | Model identifier |
| llm_latency_ms | INTEGER | NOT NULL | Classification latency |
| input_tokens | INTEGER | NULLABLE | Tokens consumed (input) |
| output_tokens | INTEGER | NULLABLE | Tokens consumed (output) |
| action_taken | VARCHAR(50) | NOT NULL | recommendation_generated/below_threshold/no_change/error |
| created_at | TIMESTAMPTZ | DEFAULT now() | |

**Indexes**: INDEX(email_message_id), INDEX(deal_id), INDEX(intent), INDEX(confidence_score), INDEX(action_taken), INDEX(created_at)
**Retention**: 30 days for LLM-specific fields, anonymize after 12 months

---

### stage_recommendations

Core workflow entity. State machine drives the entire approval workflow.

| Field | Type | Constraints | Description |
|-------|------|-------------|-------------|
| id | UUID | PK | Internal identifier |
| email_message_id | UUID | FK -> email_messages.id, NOT NULL | Triggering email |
| thread_id | UUID | FK -> email_threads.id, NOT NULL | Parent thread |
| deal_id | UUID | FK -> deals.id, NOT NULL | Target deal |
| current_stage | VARCHAR(50) | NOT NULL | Deal stage at recommendation time |
| recommended_stage | VARCHAR(50) | NOT NULL | Proposed new stage |
| recommended_stage_name | VARCHAR(255) | NOT NULL | Human-readable stage name |
| confidence_score | DECIMAL(4,3) | NOT NULL | Classification confidence |
| intent | VARCHAR(50) | NOT NULL | Classified intent |
| reasoning | TEXT | NOT NULL | Why this recommendation |
| key_phrases | TEXT[] | DEFAULT '{}' | Supporting phrases |
| direction | ENUM | NOT NULL | forward/backward/neutral |
| prompt_version | VARCHAR(20) | NOT NULL | Prompt version used |
| llm_model | VARCHAR(50) | NOT NULL | LLM model used |
| llm_latency_ms | INTEGER | NULLABLE | Classification latency |
| status | ENUM | NOT NULL, DEFAULT 'pending' | See state machine below |
| reviewed_at | TIMESTAMPTZ | NULLABLE | When user acted |
| reviewed_by | UUID | FK -> user_configs.id, NULLABLE | Who acted |
| rejection_reason | VARCHAR(50) | NULLABLE | wrong_stage/wrong_deal/not_relevant/other |
| user_corrected_stage | VARCHAR(50) | NULLABLE | Stage selected by user on rejection |
| slack_message_ts | VARCHAR(50) | NULLABLE | Slack message timestamp for updates |
| slack_channel_id | VARCHAR(50) | NULLABLE | Slack channel ID |
| snooze_count | INTEGER | DEFAULT 0 | Times snoozed |
| expires_at | TIMESTAMPTZ | NOT NULL | When recommendation expires |
| idempotency_key | VARCHAR(100) | UNIQUE, NOT NULL | rec_{id}_v{version} for CRM writes |
| created_at | TIMESTAMPTZ | DEFAULT now() | |
| updated_at | TIMESTAMPTZ | DEFAULT now() | |

**State Machine**:
```text
                    ┌──────────┐
                    │ pending  │
                    └────┬─────┘
           ┌─────────┬──┼──┬──────────┐
           │         │  │  │          │
           v         v  │  v          v
      ┌────────┐ ┌──────┴──┐  ┌──────────┐
      │approved│ │rejected │  │ snoozed  │
      └───┬────┘ └─────────┘  └────┬─────┘
          │                        │ (max 2, then)
          v                        v
    ┌─────────────┐          ┌──────────┐
    │write_success│          │ expired  │
    └─────────────┘          └──────────┘
    ┌─────────────┐
    │write_failed │          ┌──────────┐
    └─────────────┘          │superseded│
    ┌─────────────┐          └──────────┘
    │  conflict   │
    └─────────────┘

Valid transitions:
  pending -> approved, rejected, expired, superseded, snoozed
  snoozed -> pending (re-notify), expired (max snoozes reached)
  approved -> write_success, write_failed, conflict
```

**Indexes**: INDEX(deal_id, status), INDEX(status, expires_at), INDEX(reviewed_by), INDEX(created_at), UNIQUE(idempotency_key)
**Retention**: 12 months, then anonymize (remove user references)

---

### audit_logs

Immutable audit trail. INSERT and SELECT only (enforced via DB role).

| Field | Type | Constraints | Description |
|-------|------|-------------|-------------|
| id | UUID | PK | Internal identifier |
| trace_id | UUID | NULLABLE | End-to-end trace correlation |
| action | VARCHAR(100) | NOT NULL | Action performed (see list below) |
| entity_type | VARCHAR(50) | NOT NULL | Type of entity affected |
| entity_id | UUID | NOT NULL | ID of entity affected |
| actor_type | ENUM | NOT NULL, values: system/user | Who performed action |
| actor_id | VARCHAR(100) | NULLABLE | User ID or service name |
| before_state | JSONB | NULLABLE | State before action |
| after_state | JSONB | NULLABLE | State after action |
| metadata | JSONB | DEFAULT '{}' | Additional context |
| created_at | TIMESTAMPTZ | DEFAULT now(), NOT NULL | When action occurred |

**Audited Actions**: email_processed, thread_linked, intent_classified,
recommendation_generated, recommendation_approved, recommendation_rejected,
recommendation_expired, recommendation_superseded, crm_write_success,
crm_write_failed, config_changed, user_added, user_removed,
token_refreshed, token_revoked

**Indexes**: INDEX(entity_type, entity_id), INDEX(action), INDEX(actor_id), INDEX(created_at), INDEX(trace_id)
**DB Role**: audit_writer role with INSERT only; audit_reader with SELECT only. No UPDATE/DELETE grants.
**Retention**: 24 months, then archive to cold storage

---

### pipeline_configs

HubSpot pipeline mapping rules. Admin-configurable without code changes.

| Field | Type | Constraints | Description |
|-------|------|-------------|-------------|
| id | UUID | PK | Internal identifier |
| hubspot_pipeline_id | VARCHAR(50) | UNIQUE, NOT NULL | HubSpot pipeline ID |
| pipeline_name | VARCHAR(255) | NOT NULL | Human-readable name |
| stages | JSONB | NOT NULL | Stage definitions [{id, name, order}] |
| intent_to_stage_rules | JSONB | NOT NULL | {intent: stage_id} mapping |
| stage_ordering | JSONB | NOT NULL | Ordered stage list for direction validation |
| is_active | BOOLEAN | DEFAULT true | Whether pipeline is monitored |
| recommendation_threshold | DECIMAL(4,3) | DEFAULT 0.700 | Min confidence for recommendations |
| logging_threshold | DECIMAL(4,3) | DEFAULT 0.300 | Min confidence for RevOps logging |
| approval_timeout_hours | INTEGER | DEFAULT 48 | Hours before expiration |
| max_snoozes | INTEGER | DEFAULT 2 | Max snoozes per recommendation |
| created_at | TIMESTAMPTZ | DEFAULT now() | |
| updated_at | TIMESTAMPTZ | DEFAULT now() | |

**Indexes**: UNIQUE(hubspot_pipeline_id), INDEX(is_active)

---

### prompt_versions

Versioned LLM classification prompts. Only one active at a time.

| Field | Type | Constraints | Description |
|-------|------|-------------|-------------|
| id | UUID | PK | Internal identifier |
| version | VARCHAR(20) | UNIQUE, NOT NULL | Semantic version string |
| prompt_template | TEXT | NOT NULL | User prompt template with {placeholders} |
| system_prompt | TEXT | NOT NULL | System prompt for LLM |
| intent_categories | JSONB | NOT NULL | Available intent categories |
| is_active | BOOLEAN | DEFAULT false | Only one active at a time |
| created_by | UUID | FK -> user_configs.id, NULLABLE | Author |
| notes | TEXT | NULLABLE | Change notes |
| created_at | TIMESTAMPTZ | DEFAULT now() | |

**Constraints**: Partial unique index WHERE is_active = true (only one active)
**Indexes**: UNIQUE(version), INDEX(is_active)

---

### dead_messages

DLQ overflow for messages that exceed Redis retry limits.

| Field | Type | Constraints | Description |
|-------|------|-------------|-------------|
| id | UUID | PK | Internal identifier |
| component | VARCHAR(50) | NOT NULL | Originating component |
| original_payload | JSONB | NOT NULL | Original message content |
| error_message | TEXT | NOT NULL | Last error encountered |
| retry_count | INTEGER | NOT NULL | Total retry attempts |
| trace_id | UUID | NULLABLE | Correlation ID |
| first_failed_at | TIMESTAMPTZ | NOT NULL | Initial failure time |
| last_failed_at | TIMESTAMPTZ | NOT NULL | Most recent failure |
| resolved | BOOLEAN | DEFAULT false | Whether manually resolved |
| resolved_at | TIMESTAMPTZ | NULLABLE | When resolved |
| resolved_by | UUID | FK -> user_configs.id, NULLABLE | Who resolved |
| created_at | TIMESTAMPTZ | DEFAULT now() | |

**Indexes**: INDEX(component), INDEX(resolved), INDEX(first_failed_at)

---

## Validation Rules

| Entity | Rule | Source |
|--------|------|--------|
| stage_recommendations.confidence_score | 0.000 <= value <= 1.000 | FR-007 |
| stage_recommendations.snooze_count | 0 <= value <= pipeline_configs.max_snoozes | FR-020 |
| stage_recommendations.status | Valid transitions only (see state machine) | FR-014 |
| intent_classifications.confidence_score | 0.000 <= value <= 1.000 | FR-007 |
| pipeline_configs.recommendation_threshold | 0.000 <= value <= 1.000, must be > logging_threshold | FR-010 |
| pipeline_configs.logging_threshold | 0.000 <= value <= 1.000, must be < recommendation_threshold | FR-011 |
| email_messages.body_excerpt | Max 500 characters | FR-025, Principle II |
| credentials.access_token_enc | Must be AES-256 encrypted | Principle V |
| audit_logs | No UPDATE or DELETE operations permitted | Principle III |
| prompt_versions.is_active | At most one row with is_active=true | FR-027 |

---

## Data Retention Schedule

| Entity | Active Period | Action After |
|--------|--------------|--------------|
| email_messages | 6 months | DELETE |
| email_threads | 6 months | DELETE |
| intent_classifications | 12 months | Anonymize (remove user refs) |
| stage_recommendations | 12 months | Anonymize (remove user refs) |
| audit_logs | 24 months | Archive to cold storage |
| LLM-specific logs | 30 days | DELETE |
| dead_messages | Until resolved + 90 days | DELETE |
