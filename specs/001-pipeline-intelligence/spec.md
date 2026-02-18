# Feature Specification: HubSpot Pipeline Intelligence

**Feature Branch**: `001-pipeline-intelligence`
**Created**: 2026-02-15
**Status**: Draft
**Input**: HubSpot Pipeline Intelligence PRD v1.0.0 -- Phase 1 Human-in-the-Loop Pilot

## User Scenarios & Testing *(mandatory)*

### User Story 1 - Email-Triggered Deal Stage Recommendations (Priority: P1)

As a sales representative, when I send or receive a deal-related email,
the system detects the deal progression signal and delivers a stage
change recommendation to me via Slack within two minutes, so my CRM
pipeline stays current without manual data entry.

**Why this priority**: This is the core value proposition. Without
automated signal detection and recommendation delivery, the entire
system has no purpose. Every other story depends on recommendations
being generated.

**Independent Test**: Send a sales email containing a clear deal
progression signal (e.g., a pricing proposal). Verify that a Slack
notification arrives within two minutes showing the correct deal name,
current stage, recommended stage, confidence score, and a human-readable
explanation of why the stage change was detected.

**Acceptance Scenarios**:

1. **Given** a sales rep has connected their email and CRM accounts,
   **When** they send an email containing a pricing proposal to a
   contact associated with an active deal,
   **Then** the system delivers a Slack message within 2 minutes
   recommending a stage change from the current stage to "Proposal
   Sent" with a confidence score and explanation.

2. **Given** an incoming email from a contact linked to multiple deals,
   **When** the system cannot unambiguously match the email to a single
   deal,
   **Then** the email is flagged for manual deal disambiguation and
   no incorrect recommendation is generated.

3. **Given** an email that contains no deal-progression signal (e.g.,
   an out-of-office reply),
   **When** the system analyzes the email,
   **Then** no recommendation is generated and the email is logged as
   "no deal signal."

4. **Given** the system detects a signal but with low confidence
   (below the recommendation threshold),
   **When** classification completes,
   **Then** no recommendation is sent to the sales rep, but the
   classification is logged for RevOps review.

5. **Given** the system has a pending recommendation for a deal at
   stage X,
   **When** a new email triggers a recommendation for the same deal
   at a different stage Y,
   **Then** the older pending recommendation is superseded by the new
   one.

---

### User Story 2 - Recommendation Approval & CRM Writeback (Priority: P2)

As a sales representative, I can approve, reject (with corrective
feedback), or snooze a stage change recommendation directly from Slack,
and approved changes are written to my CRM automatically with a full
audit note.

**Why this priority**: Recommendations without an action pathway are
just noise. The approval workflow converts intelligence into CRM
accuracy. This story closes the loop from detection to CRM update.

**Independent Test**: Given a pending recommendation in Slack, tap
Approve and verify the deal stage in HubSpot updates within 10 seconds.
Tap Reject on another recommendation, select a reason and corrected
stage, and verify the CRM updates to the user-specified stage and the
rejection is logged.

**Acceptance Scenarios**:

1. **Given** a pending stage change recommendation in Slack,
   **When** the sales rep taps "Approve,"
   **Then** the deal stage in HubSpot is updated to the recommended
   stage, a deal note is added recording the transition details, and
   the Slack message updates to confirm success.

2. **Given** a pending recommendation,
   **When** the sales rep taps "Reject,"
   **Then** the system prompts for a rejection reason (Wrong Stage,
   Wrong Deal, Not Relevant, Other) and optionally allows the rep to
   select the correct stage for a corrective CRM update.

3. **Given** a pending recommendation,
   **When** the sales rep taps "Snooze 24h,"
   **Then** a reminder is re-sent after 24 hours, with a maximum of
   2 snoozes before the recommendation follows normal expiration.

4. **Given** a pending recommendation that has not been acted on,
   **When** 48 hours elapse (configurable timeout),
   **Then** the recommendation expires, the Slack message is updated
   to indicate expiration, and the expired item appears in the RevOps
   dashboard.

5. **Given** an approved recommendation,
   **When** the CRM write fails after retries,
   **Then** the rep is notified that their approval was recorded but
   the CRM update failed, and the operations team is alerted.

6. **Given** an approved recommendation,
   **When** the deal stage was already changed externally (conflict),
   **Then** the system detects the conflict, does not overwrite, and
   notifies the rep of both the expected and actual stages.

---

### User Story 3 - Pipeline Monitoring & Analytics Dashboard (Priority: P3)

As a RevOps analyst, I can view a web dashboard showing recommendation
acceptance rates, confidence distributions, low-confidence
classifications, and full decision trails so that I can monitor pipeline
accuracy, identify prompt improvement opportunities, and produce
trustworthy forecasts.

**Why this priority**: RevOps oversight is essential for sustained
accuracy. Without visibility into system performance, the organization
cannot tune thresholds, improve classification quality, or trust the
data for forecasting. This also provides a web-based alternative
approval interface.

**Independent Test**: Log into the dashboard, view the recommendations
feed with filters (status, confidence, date range, deal owner). Verify
that each recommendation links to its decision trail showing the
triggering email excerpt, classification result, mapping rule, user
action, and CRM outcome.

**Acceptance Scenarios**:

1. **Given** the RevOps analyst is logged into the dashboard,
   **When** they navigate to the recommendations view,
   **Then** they see a sortable, filterable list of all
   recommendations with status, deal name, confidence score, and
   timestamps.

2. **Given** the dashboard displays a recommendation,
   **When** the analyst clicks to view its Decision Trail,
   **Then** they see the full chain: email subject and excerpt ->
   classification intent and confidence -> stage mapping rule ->
   recommendation -> user action -> CRM result.

3. **Given** the analyst views the analytics section,
   **When** the page loads,
   **Then** they see metrics including: approval rate, rejection rate
   by reason, expiration rate, average confidence score, and
   email-to-notification latency.

4. **Given** low-confidence classifications exist below the
   recommendation threshold,
   **When** the analyst navigates to the "Low Confidence
   Classifications" view,
   **Then** they see flagged items with email excerpts and
   classification details for weekly review.

5. **Given** the dashboard shows pending recommendations,
   **When** the RevOps analyst uses the bulk approve/reject feature,
   **Then** multiple recommendations can be acted upon simultaneously
   with a single confirmation.

---

### User Story 4 - System Administration & Configuration (Priority: P4)

As a system administrator, I can manage user accounts, configure
pipeline-to-stage mappings, adjust confidence thresholds, manage prompt
versions, and monitor system health, so that the system remains
correctly configured, secure, and operational.

**Why this priority**: Administration is required for initial setup and
ongoing maintenance but is not part of the core value loop. It enables
the other stories to function correctly but can initially be handled
via direct configuration if the UI is not yet available.

**Independent Test**: Log into the admin panel, add a new user with
email and CRM account linking, configure a pipeline's intent-to-stage
mapping, change the recommendation confidence threshold, and verify all
changes take effect immediately and are recorded in the audit log.

**Acceptance Scenarios**:

1. **Given** the admin is logged in,
   **When** they add a new sales user,
   **Then** the user's email account is linked, CRM owner ID is
   mapped, Slack ID is associated, and the user begins receiving
   recommendations.

2. **Given** the admin navigates to pipeline configuration,
   **When** they modify the mapping between an intent category and a
   CRM stage,
   **Then** the new mapping takes effect immediately for subsequent
   classifications, and the change is audit-logged with before/after
   state.

3. **Given** the admin adjusts the recommendation confidence threshold,
   **When** a subsequent classification scores below the new threshold,
   **Then** no recommendation is generated (system respects the
   updated threshold).

4. **Given** the admin opens the prompt management view,
   **When** they edit the classification prompt and save a new version,
   **Then** the new version becomes active, the old version is
   archived, and subsequent classifications use the new prompt.

5. **Given** the admin opens the system health view,
   **When** the page loads,
   **Then** they see real-time status of all external integrations
   (email provider, CRM, messaging, AI provider) and key operational
   metrics.

---

### Edge Cases

- What happens when a sales rep has no Slack account mapped?
  The system falls back to the admin notification channel and surfaces
  the recommendation in the web dashboard.
- What happens when an email thread involves contacts from multiple
  deals? The system uses subject-line fuzzy matching and recency to
  pick the most likely deal, flagging ambiguous cases for user
  disambiguation rather than guessing.
- What happens when the AI classification service is unavailable?
  The email is queued for retry. If the primary provider fails, the
  system falls back to a secondary provider. If all providers fail,
  the email remains in a pending state and is never silently dropped.
- What happens when a deal's stage was changed manually in the CRM
  between recommendation generation and approval? The system detects
  the conflict via a read-before-write check and notifies the rep
  rather than silently overwriting.
- What happens when a rep receives more than 10 recommendations in a
  single day? This is flagged as an anti-metric. The system may need
  threshold adjustments or notification batching to prevent alert
  fatigue.
- What happens when the email provider's push notification subscription
  expires? The system renews subscriptions daily (well before the
  7-day expiry), with retry and alerting on failure. A "no emails in
  24h" detector catches silent expiration.

## Requirements *(mandatory)*

### Functional Requirements

- **FR-001**: System MUST monitor connected sales users' email inboxes
  for new messages in real time via push notifications.
- **FR-002**: System MUST renew email monitoring subscriptions daily,
  with retry and alerting on failure, to prevent silent monitoring gaps.
- **FR-003**: On initial user onboarding, system MUST sync the last 14
  days of email (up to 500 messages) for thread context.
- **FR-004**: System MUST group emails into conversation threads and
  link threads to CRM deals by resolving email participants to CRM
  contacts and their associated deals.
- **FR-005**: System MUST cache contact-to-deal resolution results with
  a 1-hour time-to-live to reduce external API calls.
- **FR-006**: For multi-deal matches, system MUST use subject-line
  fuzzy matching and recency ranking, flagging truly ambiguous cases
  for user disambiguation.
- **FR-007**: System MUST classify each deal-linked email for deal
  progression intent using AI, returning: intent category, confidence
  score (0.0-1.0), reasoning, key phrases, and direction
  (forward/backward/neutral).
- **FR-008**: System MUST support a configurable set of intent
  categories (default 13: discovery_call_scheduled, demo_scheduled,
  demo_completed, proposal_requested, proposal_sent,
  negotiation_active, verbal_commitment, contract_sent, closed_won,
  closed_lost, objection_raised, deal_stalled, no_deal_signal).
- **FR-009**: System MUST include current deal stage and recent email
  thread summaries in the classification context to prevent illogical
  classifications.
- **FR-010**: System MUST enforce a configurable confidence threshold
  (default: 0.70) below which no user-facing recommendation is
  generated.
- **FR-011**: Below-threshold classifications MUST be logged and
  surfaced for RevOps review if above a secondary logging threshold
  (default: 0.30).
- **FR-012**: System MUST map classified intents to CRM pipeline stages
  via configurable mapping rules, supporting multiple pipelines with
  independent stage configurations.
- **FR-013**: System MUST enforce stage ordering: backward stage
  movement MUST only occur when the classification explicitly indicates
  regression (e.g., objection_raised, deal_stalled, closed_lost).
- **FR-014**: System MUST generate a recommendation only when all
  conditions are met: email linked to deal, confidence above threshold,
  mapped stage differs from current stage, and no duplicate pending
  recommendation exists for the same deal and stage.
- **FR-015**: System MUST deliver recommendations via Slack interactive
  messages to the deal owner, including: deal name, current and
  recommended stage, confidence score (color-coded), reasoning, and
  action buttons (Approve, Reject, Snooze 24h).
- **FR-016**: System MUST support a web dashboard as an alternative
  approval interface with sortable, filterable lists and bulk
  approve/reject for RevOps users.
- **FR-017**: On approval, system MUST update the CRM deal stage and
  add an audit note recording: stage transition, triggering email,
  confidence score, approver identity, and timestamp.
- **FR-018**: On rejection, system MUST capture a rejection reason
  (Wrong Stage, Wrong Deal, Not Relevant, Other) and optionally allow
  the rep to select a corrected stage for an alternative CRM update.
- **FR-019**: Unanswered recommendations MUST expire after a
  configurable timeout (default: 48 hours) with the Slack message
  updated and the item surfaced in the RevOps dashboard.
- **FR-020**: System MUST support a maximum of 2 snoozes per
  recommendation (configurable).
- **FR-021**: Before writing to the CRM, system MUST read the current
  deal state to detect external modifications (conflicts). Conflicts
  MUST be reported to the user, never silently overwritten.
- **FR-022**: System MUST record an immutable audit log entry for
  every significant action: email processed, thread linked, intent
  classified, recommendation generated/approved/rejected/expired/
  superseded, CRM write success/failure, configuration changed, user
  added/removed.
- **FR-023**: System MUST provide a "Decision Trail" view
  reconstructing the full chain from email to CRM outcome for any
  recommendation.
- **FR-024**: System MUST redact personally identifiable information
  (phone numbers, government IDs, financial account numbers) from
  email content before sending it to external AI providers. Email
  addresses and names are retained (required for contact resolution).
- **FR-025**: System MUST NOT store full email bodies. After
  classification, only metadata and a 500-character excerpt are
  retained.
- **FR-026**: System MUST support right-to-deletion: all records for a
  given contact are purged within 30 days of a deletion request.
- **FR-027**: System MUST version AI classification prompts in the
  configuration store (not hardcoded). Each classification MUST record
  the prompt version used. Admins MUST be able to view, edit, version,
  and rollback prompts.
- **FR-028**: System MUST support three user roles: admin (full system
  access), revops (pipeline configuration, thresholds, analytics, bulk
  review), sales_user (own recommendations and history only).
- **FR-029**: Admin dashboard MUST provide: user management, pipeline
  configuration, threshold management, prompt management, and system
  health monitoring.
- **FR-030**: All configuration changes MUST be audit-logged with
  before/after state and actor identity.

### Key Entities

- **Email Message**: A single email received or sent by a monitored
  user. Key attributes: sender, recipients, subject, 500-char excerpt,
  timestamps, processing status, conversation thread membership.
- **Email Thread**: A conversation thread grouping related email
  messages and linked to a specific CRM deal. Key attributes: thread
  identifier, linked deal, participant contacts, message count, last
  activity.
- **Deal**: A cached representation of a CRM deal. Key attributes:
  deal name, current stage, pipeline membership, deal owner, associated
  contacts, amount, expected close date.
- **Intent Classification**: The AI's analysis of a single email. Key
  attributes: detected intent, confidence score, reasoning, key
  phrases, direction, prompt version used, AI model used.
- **Stage Recommendation**: The core workflow entity representing a
  proposed deal stage change. Key attributes: linked email, linked
  deal, current stage, recommended stage, confidence score, status
  (pending/approved/rejected/expired/superseded/conflict/write_failed),
  reviewer identity, rejection reason, snooze count, expiration time.
- **Audit Log Entry**: An immutable record of a system action. Key
  attributes: action type, entity type and ID, actor, before/after
  state, timestamp, trace identifier.
- **User Profile**: A system user with linked external accounts. Key
  attributes: email, display name, role (admin/revops/sales_user),
  CRM owner ID, messaging account ID, email monitoring status.
- **Pipeline Configuration**: Mapping rules for a CRM pipeline. Key
  attributes: pipeline identity, stage definitions, intent-to-stage
  mapping rules, stage ordering, confidence thresholds, approval
  timeout settings.
- **Prompt Version**: A versioned AI classification prompt. Key
  attributes: version number, prompt template, system instructions,
  intent categories, active flag, author, notes.

## Success Criteria *(mandatory)*

### Measurable Outcomes

- **SC-001**: Average deal stage lag reduced from 4-7 days to less
  than 1 day by Week 12 of the pilot.
- **SC-002**: Percentage of deals updated within 24 hours of a
  progression signal increases from ~30% to over 80%.
- **SC-003**: Weekly manual CRM update time per sales rep reduced from
  ~45 minutes to less than 10 minutes.
- **SC-004**: Pipeline forecast accuracy (RevOps) improves from +/-30%
  variance to +/-15%.
- **SC-005**: Recommendation accuracy (approved / total reviewed)
  exceeds 65% by Week 4 and 80% by Week 12.
- **SC-006**: User adoption rate (percentage of pilot users active per
  week) exceeds 60% by Week 4 and 80% by Week 12.
- **SC-007**: Stage change recommendations delivered within 60 seconds
  of email receipt (median) and within 120 seconds (95th percentile).
- **SC-008**: CRM updates written within 3 seconds of approval
  (median) and within 10 seconds (95th percentile).
- **SC-009**: Deal coverage (percentage of active deals with linked
  email threads) exceeds 50% by Week 4 and 75% by Week 12.
- **SC-010**: Recommendation expiration rate stays below 25%.
- **SC-011**: System uptime exceeds 99.5% during the 12-week pilot.
- **SC-012**: No email is silently lost -- every processed email has a
  traceable audit record.
- **SC-013**: User satisfaction (NPS) exceeds 50 at the Week 12 survey.
- **SC-014**: RevOps team reports saving at least 4 hours per week on
  pipeline data cleaning by Week 12.

## Assumptions

- The pilot targets 10-20 internal users over a 12-week window.
- All pilot users use Gmail as their email provider and HubSpot as
  their CRM.
- All pilot users have active Slack accounts for receiving
  notifications.
- The organization has an existing Google Cloud Platform project
  available for infrastructure.
- HubSpot deal pipelines and stages are already configured and stable;
  the system maps to existing pipelines, it does not create new ones.
- The AI classification model achieves at least 85% accuracy on
  well-scoped intent classification tasks based on current model
  capabilities.
- Sales reps manage 30-50 active deals each and generate approximately
  50-100 emails per day collectively across the pilot group.
- The organization's privacy policy permits processing sales email
  metadata with AI providers configured for zero data retention.
- Authentication uses the organization's existing SSO provider
  (Google Workspace) for the web dashboard.

## Scope Boundaries

**In scope for Phase 1 (this specification):**
- Gmail email monitoring via real-time push notifications
- Email thread identification and linking to existing HubSpot deals
- AI-based intent classification of email content
- Confidence-scored stage change recommendations
- Human-in-the-loop approval via Slack and web dashboard
- HubSpot deal stage updates upon approval
- Full audit trail for every system action
- Admin configuration for pipeline mappings, thresholds, and users
- Structured logging and operational monitoring

**Explicitly out of scope:**
- Autonomous CRM updates without human approval
- Non-Gmail email providers (Outlook, Yahoo)
- Non-HubSpot CRMs (Salesforce, Pipedrive)
- Deal creation (only stage progression on existing deals)
- Contact creation or enrichment
- Email sending or reply generation
- Calendar or meeting analysis
- Revenue forecasting or predictive analytics
- Mobile application
- Multi-tenant deployment
- Browser extensions or email add-ons
