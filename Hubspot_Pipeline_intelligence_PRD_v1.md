HubSpot Pipeline Intelligence -- Product Requirements Document (PRD)

 Version: 1.0.0-draft
 Author: Senior Staff Product Manager / Enterprise Architect
 Date: 2026-02-09
 Status: Design Phase -- Implementation Pending
 Classification: Internal Engineering Document

 ---
 Context

 Why this change is being made:

 Sales representatives conduct deal-advancing conversations via email, but CRM deal stages in HubSpot are not updated to reflect reality. Reps are incentivized to sell, not to maintain data hygiene. The result: pipeline data lags reality by 4-7 days,
  forecasts carry 20-40% variance, and leadership makes resource decisions on stale information.

 The root cause is structural -- the signal that a deal has advanced lives in email threads and is never systematically extracted back into the CRM. We are building a pipeline intelligence system that monitors email, uses LLM-based intent
 classification to detect deal progression signals, generates human-reviewed stage change recommendations, and writes approved updates back to HubSpot.

 This is Phase 1: a human-in-the-loop pilot for 10-20 internal users.

 ---
 Table of Contents

 1. #1-executive-summary
 2. #2-strategic-context
 3. #3-product-overview
 4. #4-personas
 5. #5-user-journeys
 6. #6-functional-requirements
 7. #7-non-functional-requirements
 8. #8-system-architecture
 9. #9-data-model
 10. #10-dependencies
 11. #11-risks--mitigations
 12. #12-success-metrics
 13. #13-roadmap-outlook
 14. #appendices

 ---
 1. Executive Summary

 1.1 Problem Statement

 Sales representatives spend an average of 5.5 hours per week on CRM data entry. In organizations using HubSpot, deal stages frequently lag actual deal progression by days or weeks because updates depend on manual action from reps. The CRM reflects a
  pipeline state 1-3 weeks behind reality. RevOps teams producing forecasts from this data generate projections with 20-40% variance from actual outcomes. Leadership decisions on hiring, territory planning, and resource allocation are made on stale
 information.

 1.2 Vision

 Build an intelligence layer that monitors sales email conversations, classifies deal-progression signals using LLM-based intent analysis, and generates human-reviewed recommendations to update HubSpot deal stages. The system acts as an always-on
 deal-stage analyst that surfaces what the CRM should say, while keeping a human in the approval loop.

 1.3 Expected Quantifiable Impact (Pilot: 10-20 Users, 12-Week Window)
 ┌─────────────────────────────────────────┬──────────────────────┬──────────┐
 │                 Metric                  │ Baseline (Estimated) │  Target  │
 ├─────────────────────────────────────────┼──────────────────────┼──────────┤
 │ Average deal stage lag                  │ 4-7 days             │ < 1 day  │
 ├─────────────────────────────────────────┼──────────────────────┼──────────┤
 │ % of deals updated within 24h of signal │ ~30%                 │ > 80%    │
 ├─────────────────────────────────────────┼──────────────────────┼──────────┤
 │ Weekly manual CRM update time per rep   │ ~45 min              │ < 10 min │
 ├─────────────────────────────────────────┼──────────────────────┼──────────┤
 │ Pipeline forecast accuracy (RevOps)     │ +/- 30%              │ +/- 15%  │
 ├─────────────────────────────────────────┼──────────────────────┼──────────┤
 │ % of deal-related emails linked to CRM  │ ~15% (manual)        │ > 75%    │
 └─────────────────────────────────────────┴──────────────────────┴──────────┘
 ---
 2. Strategic Context

 2.1 Why CRM Adoption Fails in Enterprises

 CRM data quality degrades because the incentive structure is misaligned. The person who generates the signal (the sales rep) bears the cost of data entry but receives none of the benefit (which accrues to management and RevOps). This is a classic
 principal-agent problem. Training, gamification, and mandatory fields have been tried for two decades and have not solved it. The only durable solution is to remove the rep from the data-entry loop entirely, or reduce their burden to a single
 approval action.

 2.2 AI Transformation Alignment

 Large language models have reached sufficient capability to perform intent classification on unstructured email text with accuracy exceeding 85% on well-scoped classification tasks. The cost of classification has dropped to under $0.01 per email
 using models like Claude Haiku 4.5. This makes it economically viable to classify every inbound/outbound sales email in real time. The missing piece is not the AI -- it is the end-to-end system that connects email ingestion, classification, human
 review, and CRM writeback into a reliable pipeline.

 2.3 Competitive Landscape

 This is an internal tool for pilot deployment. Competitor landscape includes Gong (call-based, not email-first), Clari (forecasting layer, not email-to-CRM), and People.ai (activity capture, but no LLM-based intent classification with
 human-in-the-loop). The differentiation is the tight loop: email signal -> LLM classification -> human approval -> CRM write, with full explainability at each step.

 ---
 3. Product Overview

 3.1 In Scope

 - Gmail email monitoring via Push Notifications (Google Cloud Pub/Sub)
 - Email thread identification and linking to HubSpot deals
 - LLM-based intent classification of email content
 - Confidence-scored stage change recommendations
 - Human-in-the-loop approval via Slack interactive messages and web dashboard
 - HubSpot deal stage updates upon approval
 - Full audit trail of every classification, recommendation, approval/rejection, and CRM write
 - Admin configuration UI for pipeline mapping, confidence thresholds, user management
 - Structured logging and observability

 3.2 Out of Scope

 - Autonomous CRM updates (no auto-approve, no auto-write)
 - Browser extension or Gmail add-on
 - Email sending or reply generation
 - Calendar or meeting analysis
 - Non-HubSpot CRMs (Salesforce, Pipedrive)
 - Non-Gmail email providers (Outlook, Yahoo)
 - Deal creation (only stage progression on existing deals)
 - Contact creation or enrichment
 - Revenue forecasting or predictive analytics
 - Mobile application
 - Multi-tenant SaaS deployment

 3.3 Target Users
 ┌───────────────────────────┬───────────────┬──────────────────────────────────────────────────────────┐
 │           Role            │ Count (Pilot) │                   Primary Interaction                    │
 ├───────────────────────────┼───────────────┼──────────────────────────────────────────────────────────┤
 │ Sales Representatives     │ 10-15         │ Slack notifications, approve/reject recommendations      │
 ├───────────────────────────┼───────────────┼──────────────────────────────────────────────────────────┤
 │ RevOps / Sales Operations │ 2-3           │ Dashboard monitoring, pipeline config, analytics review  │
 ├───────────────────────────┼───────────────┼──────────────────────────────────────────────────────────┤
 │ System Administrator      │ 1-2           │ Integration management, user provisioning, system health │
 └───────────────────────────┴───────────────┴──────────────────────────────────────────────────────────┘
 ---
 4. Personas

 4.1 Sarah -- Account Executive (Sales User)

 Profile: 28 years old, 4 years in B2B SaaS sales, manages 30-50 active deals.

 Pain Points:
 - Spends 30-60 minutes daily on CRM updates that feel like busywork
 - Gets flagged in pipeline reviews for deals that are further along than HubSpot shows
 - Has lost deals because a manager reallocated resources based on stale pipeline data
 - Distrusts the CRM because her own data entry is inconsistent

 Goals:
 - Keep HubSpot accurate without manual effort
 - Have management see the true state of her pipeline without explanation
 - Spend more time selling, less time on admin tasks

 Interaction with System: Receives a Slack message: "Based on your email exchange with John at Acme Corp, it looks like 'Acme Enterprise License' has moved from 'Demo Scheduled' to 'Proposal Sent'. Approve?" Sarah taps "Approve" in Slack and moves
 on.

 4.2 Marcus -- Revenue Operations Analyst (RevOps User)

 Profile: 32 years old, 6 years in RevOps/Sales Ops, responsible for pipeline reporting and forecast accuracy.

 Pain Points:
 - Spends the first 2 days of every week cleaning pipeline data before producing the forecast
 - Cannot trust stage timestamps because reps batch-update on Fridays
 - Has no visibility into email-level deal activity
 - Gets blamed when forecast misses, despite the root cause being bad input data

 Goals:
 - Achieve pipeline data that reflects reality within 24 hours
 - Reduce time spent on data cleaning from 2 days/week to < 2 hours
 - Have evidence-based confidence in stage transitions (what email triggered the change)

 Interaction with System: Logs into the web dashboard to see recommendation acceptance rates, average confidence scores, and a feed of recent stage changes with the email evidence that triggered each one.

 4.3 David -- IT/Systems Administrator (Admin User)

 Profile: 35 years old, 8 years in IT/SysAdmin roles, manages the company's SaaS integrations.

 Pain Points:
 - Every new integration is a potential security risk and maintenance burden
 - Gets paged when integrations break
 - Has no visibility into what data third-party tools are accessing
 - Compliance team asks quarterly about data handling for every integration

 Goals:
 - Deploy integrations that are secure, observable, and low-maintenance
 - Have clear audit trails for compliance reporting
 - Minimize the blast radius of any single integration failure

 Interaction with System: Configures OAuth connections for Gmail and HubSpot, sets up Slack workspace integration, monitors system health dashboard, manages user access, responds to alerts.

 ---
 5. User Journeys

 5.1 Journey 1: Happy Path

 Step 1:  Sarah sends an email to John at Acme Corp with a pricing proposal.
 Step 2:  Gmail sends a push notification to Google Cloud Pub/Sub (historyId change).
 Step 3:  Ingestion Service receives the Pub/Sub message, pulls the email via
          Gmail API using history.list.
 Step 4:  Thread Linker matches the email thread to HubSpot deal "Acme Enterprise
          License" by resolving john@acmecorp.com -> HubSpot Contact ID 12345 ->
          Deal ID 67890.
 Step 5:  Intent Analyzer sends the email body (with PII redaction) to the LLM.
          LLM returns:
          {
            "intent": "proposal_sent",
            "confidence": 0.91,
            "reasoning": "Email contains pricing proposal attachment and language
                          indicating formal offer.",
            "key_phrases": ["Please find attached our proposal"],
            "direction": "forward"
          }
 Step 6:  Stage Mapper maps intent "proposal_sent" -> HubSpot stage "Proposal Sent"
          (stage ID: hs_stage_004).
 Step 7:  Recommendation Engine generates StageRecommendation:
          current_stage: "Demo Completed", recommended_stage: "Proposal Sent",
          confidence: 0.91, status: "pending"
 Step 8:  Notification Service sends Slack interactive message to Sarah:
          "Deal: Acme Enterprise License
           Demo Completed -> Proposal Sent (91% confidence)
           Reason: Your email to John contained a pricing proposal.
           [Approve] [Reject] [Snooze 24h]"
 Step 9:  Sarah taps [Approve].
 Step 10: CRM Updater calls HubSpot API PATCH /crm/v3/objects/deals/67890
          with { "dealstage": "hs_stage_004" }.
 Step 11: AuditLog records the full chain.
 Step 12: Slack message updates to "Approved -- HubSpot updated."

 End-to-end latency target: < 120 seconds from email send to Slack notification.

 5.2 Journey 2: Failure Flow

 Scenario A -- HubSpot Rate Limit at Thread Linking:
 Step 4:  Thread Linker calls HubSpot API, receives HTTP 429.
 Step 4a: System retries with exponential backoff: 1s, 2s, 4s, 8s (max 4 retries).
 Step 4b: If all retries fail -> message placed in Dead Letter Queue (DLQ).
 Step 4c: Alert fires to #pipeline-intelligence-alerts Slack channel.
 Step 4d: DLQ processor retries every 15 minutes with jittered backoff.

 Scenario B -- LLM Failure at Intent Analysis:
 Step 5:  Intent Analyzer calls Claude API, receives HTTP 500 or timeout.
 Step 5a: Retry with backoff: 2s, 4s, 8s (max 3 retries).
 Step 5b: If primary fails, fall back to secondary LLM provider (OpenAI GPT-4o-mini).
 Step 5c: If all providers fail -> email queued for retry, alert fires.
 Step 5d: Email remains in "pending_classification" state (never silently dropped).

 Scenario C -- CRM Write Conflict:
 Step 10: CRM Updater calls HubSpot API, receives HTTP 409 (deal modified externally).
 Step 10a: System re-reads deal state from HubSpot.
 Step 10b: If stage matches our recommendation -> mark "completed_externally."
 Step 10c: If stage differs -> mark "conflict," notify Sarah with both stages.

 5.3 Journey 3: Low Confidence Flow

 Step 5:  Intent Analyzer returns confidence: 0.42 (below RECOMMENDATION_THRESHOLD 0.70).
 Step 6:  System does NOT generate a user-facing recommendation.
 Step 6a: Classification logged for training data:
          { email_id, intent, confidence, reasoning, action: "below_threshold" }
 Step 6b: If confidence > LOGGING_THRESHOLD (0.30): flagged for RevOps review in
          dashboard under "Low Confidence Classifications."
 Step 6c: If confidence < 0.30: logged only, not surfaced in any UI.
 Step 7:  Marcus (RevOps) reviews low-confidence items weekly to identify prompt
          improvement opportunities.

 5.4 Journey 4: Approval/Rejection Flow

 REJECTION:
 Step 9:  Sarah taps [Reject] in Slack.
 Step 9a: System presents follow-up: "Why? [Wrong stage] [Wrong deal] [Not relevant] [Other]"
 Step 9b: Sarah selects [Wrong stage].
 Step 9c: System presents pipeline stages for correct selection.
 Step 9d: Sarah selects [Negotiation].
 Step 9e: System asks: "Update deal to 'Negotiation'? [Yes] [No, just reject]"
 Step 9f: Sarah selects [Yes] -> CRM updated to user-specified stage.
 Step 9g: AuditLog: recommendation rejected, rejection_reason="wrong_stage",
          user_corrected_stage="Negotiation". Fed back as training signal.

 EXPIRATION:
 Step 9:  No response within 48 hours (configurable APPROVAL_TIMEOUT).
 Step 9a: Status transitions to "expired."
 Step 9b: Slack message updated: "This recommendation has expired."
 Step 9c: Expired recommendations surfaced in RevOps dashboard.

 SNOOZE:
 Step 9:  Sarah taps [Snooze 24h].
 Step 9a: Reminder sent in 24 hours. Max 2 snoozes, then normal expiration.

 ---
 6. Functional Requirements

 FR-01: Email Monitoring
 ┌─────────┬──────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────┐
 │   ID    │                                                                   Requirement                                                                    │
 ├─────────┼──────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────┤
 │ FR-01.1 │ SHALL use Gmail API users.watch to register push notifications for each user's mailbox                                                           │
 ├─────────┼──────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────┤
 │ FR-01.2 │ Watch SHALL be scoped to labelIds: ["INBOX", "SENT"]. OAuth scope: gmail.readonly                                                                │
 ├─────────┼──────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────┤
 │ FR-01.3 │ SHALL create GCP Pub/Sub topic projects/{project-id}/topics/gmail-push-notifications with gmail-api-push@system.gserviceaccount.com as Publisher │
 ├─────────┼──────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────┤
 │ FR-01.4 │ SHALL create a pull subscription for debuggability in pilot                                                                                      │
 ├─────────┼──────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────┤
 │ FR-01.5 │ SHALL renew users.watch daily at 02:00 UTC (watches expire after 7 days). Retry 3x with backoff on failure, alert on final failure               │
 ├─────────┼──────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────┤
 │ FR-01.6 │ On Pub/Sub notification { emailAddress, historyId }, SHALL call users.history.list with startHistoryId = last processed historyId                │
 ├─────────┼──────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────┤
 │ FR-01.7 │ SHALL store latest processed historyId per user to prevent duplicates and gaps                                                                   │
 ├─────────┼──────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────┤
 │ FR-01.8 │ On initial onboarding, SHALL sync last 14 days of email (max 500 messages) for thread context                                                    │
 ├─────────┼──────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────┤
 │ FR-01.9 │ SHALL handle Gmail API errors: 401 -> re-auth, 403 -> alert, 429 -> backoff+retry, 404 -> deactivate+alert                                       │
 └─────────┴──────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────┘
 FR-02: Thread Linking
 ┌─────────┬──────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────┐
 │   ID    │                                                                                 Requirement                                                                                  │
 ├─────────┼──────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────┤
 │ FR-02.1 │ SHALL use Gmail threadId to group emails into conversation threads                                                                                                           │
 ├─────────┼──────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────┤
 │ FR-02.2 │ SHALL resolve email addresses (From/To/CC) to HubSpot Contact IDs via GET /crm/v3/objects/contacts/search                                                                    │
 ├─────────┼──────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────┤
 │ FR-02.3 │ SHALL resolve Contacts to Deals via GET /crm/v4/objects/contacts/{contactId}/associations/deals                                                                              │
 ├─────────┼──────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────┤
 │ FR-02.4 │ For multi-deal matches: (1) fuzzy match email subject to deal name, (2) prefer deal with recent activity, (3) if ambiguous, flag as multi_deal_match for user disambiguation │
 ├─────────┼──────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────┤
 │ FR-02.5 │ Contact resolution results SHALL be cached in Redis with 1-hour TTL                                                                                                          │
 ├─────────┼──────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────┤
 │ FR-02.6 │ If no HubSpot contact found for any address, log as unlinked, do not process further. Visible in admin dashboard                                                             │
 ├─────────┼──────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────┤
 │ FR-02.7 │ SHALL maintain EmailThread entity persisting Gmail thread ID -> HubSpot deal ID mapping. Once linked, subsequent emails reuse linkage without re-resolving                   │
 └─────────┴──────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────┘
 FR-03: Intent Analysis
 ID: FR-03.1
 Requirement: SHALL send email body, subject, sender, recipients to LLM for classification. Provider configurable via env var
 ────────────────────────────────────────
 ID: FR-03.2
 Requirement: SHALL classify into configurable intent categories (default 13: discovery_call_scheduled, demo_scheduled, demo_completed, proposal_requested, proposal_sent, negotiation_active, verbal_commitment, contract_sent, closed_won, closed_lost,
   objection_raised, deal_stalled, no_deal_signal)
 ────────────────────────────────────────
 ID: FR-03.3
 Requirement: LLM SHALL return structured JSON: { intent, confidence (0.0-1.0), reasoning, key_phrases[], direction (forward/backward/neutral) }
 ────────────────────────────────────────
 ID: FR-03.4
 Requirement: Prompt SHALL include current deal stage and last 2-3 email summaries for context to prevent illogical classifications
 ────────────────────────────────────────
 ID: FR-03.5
 Requirement: Default model: Claude Haiku 4.5. Estimated cost: ~$0.002/classification
 ────────────────────────────────────────
 ID: FR-03.6
 Requirement: Token budget: 4,096 input tokens, 512 output tokens. Emails exceeding limit truncated from middle (preserve first 1,024 and last 1,024 tokens)
 ────────────────────────────────────────
 ID: FR-03.7
 Requirement: 15-second timeout on LLM calls. Timeout -> retry once at 30s before entering failure flow
 ────────────────────────────────────────
 ID: FR-03.8
 Requirement: Prompt SHALL be versioned in database (not hardcoded). Each classification records prompt version used
 FR-04: Stage Mapping
 ┌─────────┬──────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────┐
 │   ID    │                                                                             Requirement                                                                              │
 ├─────────┼──────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────┤
 │ FR-04.1 │ SHALL maintain PipelineConfig mapping LLM intent categories -> HubSpot stage IDs (many-to-one)                                                                       │
 ├─────────┼──────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────┤
 │ FR-04.2 │ SHALL support multiple HubSpot pipelines, each with its own stage mappings                                                                                           │
 ├─────────┼──────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────┤
 │ FR-04.3 │ SHALL enforce stage ordering: no backward movement unless intent explicitly indicates regression (objection_raised, deal_stalled, closed_lost). Uses direction field │
 ├─────────┼──────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────┤
 │ FR-04.4 │ SHALL validate recommended stage is valid in target pipeline (cached pipeline metadata, refreshed every 6 hours)                                                     │
 ├─────────┼──────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────┤
 │ FR-04.5 │ Admin SHALL configure stage mappings via web dashboard without code changes                                                                                          │
 ├─────────┼──────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────┤
 │ FR-04.6 │ If intent maps to current stage (no change needed), no recommendation generated. Logged as no_change_needed                                                          │
 └─────────┴──────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────┘
 FR-05: Recommendation Generation
 ┌─────────┬──────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────┐
 │   ID    │                                                                                                           Requirement                                                                                                            │
 ├─────────┼──────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────┤
 │ FR-05.1 │ SHALL generate recommendation ONLY when: (1) email linked to deal, (2) confidence >= RECOMMENDATION_THRESHOLD (default: 0.70), (3) mapped stage differs from current, (4) no existing pending recommendation for same deal+stage │
 ├─────────┼──────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────┤
 │ FR-05.2 │ Recommendation SHALL include: deal_id, current_stage, recommended_stage, confidence_score, reasoning, key_phrases, email_message_id, thread_id, prompt_version, status, created_at                                               │
 ├─────────┼──────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────┤
 │ FR-05.3 │ If new recommendation generated for deal with existing PENDING recommendation for DIFFERENT stage, older SHALL be superseded                                                                                                     │
 ├─────────┼──────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────┤
 │ FR-05.4 │ SHALL assemble context package for approval UI: deal name, current/recommended stage, confidence %, reasoning, key phrases, HubSpot link, Gmail thread link                                                                      │
 └─────────┴──────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────┘
 FR-06: Approval Workflow
 ┌─────────┬────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────┐
 │   ID    │                                                                                                  Requirement                                                                                                   │
 ├─────────┼────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────┤
 │ FR-06.1 │ SHALL send Slack Block Kit messages with: deal name, stage transition, confidence (color-coded: green >= 85%, yellow 70-84%), reasoning (max 280 chars), [Approve] [Reject] [Snooze 24h] buttons, HubSpot link │
 ├─────────┼────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────┤
 │ FR-06.2 │ Message sent to deal owner's Slack. Fallback: admin notification channel if no Slack mapping                                                                                                                   │
 ├─────────┼────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────┤
 │ FR-06.3 │ SHALL handle Slack interaction payloads at POST /api/slack/interactions with signature verification                                                                                                            │
 ├─────────┼────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────┤
 │ FR-06.4 │ On Rejection: secondary prompt for reason (Wrong Stage, Wrong Deal, Not Relevant, Other) and optional correct stage selection                                                                                  │
 ├─────────┼────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────┤
 │ FR-06.5 │ Web dashboard SHALL provide alternative approval interface with filterable/sortable list and bulk approve/reject for RevOps                                                                                    │
 ├─────────┼────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────┤
 │ FR-06.6 │ Recommendations expire after APPROVAL_TIMEOUT hours (default: 48). Slack message updated on expiration                                                                                                         │
 ├─────────┼────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────┤
 │ FR-06.7 │ Maximum 2 snoozes per recommendation (configurable)                                                                                                                                                            │
 └─────────┴────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────┘
 FR-07: CRM Update
 ┌─────────┬─────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────┐
 │   ID    │                                                           Requirement                                                           │
 ├─────────┼─────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────┤
 │ FR-07.1 │ On approval, SHALL call PATCH /crm/v3/objects/deals/{dealId} with { "dealstage": "{target_stage_id}" }                          │
 ├─────────┼─────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────┤
 │ FR-07.2 │ SHALL read current deal state before writing to detect conflicts                                                                │
 ├─────────┼─────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────┤
 │ FR-07.3 │ SHALL implement idempotency via unique key per recommendation (rec_{id}_v{version})                                             │
 ├─────────┼─────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────┤
 │ FR-07.4 │ SHALL add HubSpot deal note with: stage transition, trigger email, confidence, approver, timestamp                              │
 ├─────────┼─────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────┤
 │ FR-07.5 │ SHALL rate-limit HubSpot API calls via Redis-backed token bucket (110 req/10s for OAuth apps)                                   │
 ├─────────┼─────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────┤
 │ FR-07.6 │ If write fails after 3 retries, mark as write_failed, notify user: "Approval recorded but HubSpot update failed. Team alerted." │
 └─────────┴─────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────┘
 FR-08: Logging & Observability
 ID: FR-08.1
 Requirement: All logs SHALL be structured JSON: timestamp, level, service, trace_id, span_id, user_id, message, metadata
 ────────────────────────────────────────
 ID: FR-08.2
 Requirement: Every processing step SHALL carry a trace_id (UUID from Pub/Sub receipt) for end-to-end tracing
 ────────────────────────────────────────
 ID: FR-08.3
 Requirement: SHALL emit Prometheus-compatible metrics: emails_received_total, emails_linked_total, classifications_total, recommendations_generated/approved/rejected/expired_total, crm_updates_total, llm_latency_seconds,
   email_to_recommendation_latency_seconds, hubspot_api_latency_seconds, dlq_depth
 ────────────────────────────────────────
 ID: FR-08.4
 Requirement: SHALL alert (Slack webhook) for: DLQ depth > 50, LLM error rate > 10%/5min, HubSpot error rate > 5%/5min, watch renewal failure, no emails processed for active user in 24h
 ────────────────────────────────────────
 ID: FR-08.5
 Requirement: Logs shipped to centralized logging system with 90-day retention
 FR-09: Admin Configuration
 ID: FR-09.1
 Requirement: Dashboard SHALL provide: user management (add/remove, OAuth linking, Slack/HubSpot ID mapping), pipeline configuration (pipeline selection, intent-to-stage mapping), threshold configuration (RECOMMENDATION_THRESHOLD, LOGGING_THRESHOLD,
   APPROVAL_TIMEOUT, MAX_SNOOZES), prompt management (view/edit/version/rollback), system health (real-time metrics)
 ────────────────────────────────────────
 ID: FR-09.2
 Requirement: All config changes SHALL be audit-logged with before/after state and actor
 ────────────────────────────────────────
 ID: FR-09.3
 Requirement: RBAC: admin (full access), revops (pipeline config, thresholds, analytics, batch review), sales_user (own recommendations and history only)
 ---
 7. Non-Functional Requirements

 NFR-01: Security
 ┌──────────┬──────────────────────────────────────────────────────────────────────────────────────────────────────────────┐
 │    ID    │                                                 Requirement                                                  │
 ├──────────┼──────────────────────────────────────────────────────────────────────────────────────────────────────────────┤
 │ NFR-01.1 │ All OAuth tokens (Gmail, HubSpot, Slack) SHALL be AES-256 encrypted at rest in a dedicated credentials table │
 ├──────────┼──────────────────────────────────────────────────────────────────────────────────────────────────────────────┤
 │ NFR-01.2 │ Token refresh SHALL happen proactively: Gmail at 45 min (expires 1h), HubSpot at 5h (expires 6h)             │
 ├──────────┼──────────────────────────────────────────────────────────────────────────────────────────────────────────────┤
 │ NFR-01.3 │ All external API calls SHALL use HTTPS/TLS 1.2+                                                              │
 ├──────────┼──────────────────────────────────────────────────────────────────────────────────────────────────────────────┤
 │ NFR-01.4 │ Web dashboard auth via org SSO (Google Workspace OIDC for pilot)                                             │
 ├──────────┼──────────────────────────────────────────────────────────────────────────────────────────────────────────────┤
 │ NFR-01.5 │ RBAC enforced at API layer. Unauthorized access logged and alerted                                           │
 ├──────────┼──────────────────────────────────────────────────────────────────────────────────────────────────────────────┤
 │ NFR-01.6 │ Secrets stored in secrets manager (GCP Secret Manager) in production. .env files for local dev only          │
 ├──────────┼──────────────────────────────────────────────────────────────────────────────────────────────────────────────┤
 │ NFR-01.7 │ Slack interaction webhook SHALL validate X-Slack-Signature on every request                                  │
 └──────────┴──────────────────────────────────────────────────────────────────────────────────────────────────────────────┘
 NFR-02: Privacy
 ┌──────────┬─────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────┐
 │    ID    │                                                                                     Requirement                                                                                     │
 ├──────────┼─────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────┤
 │ NFR-02.1 │ SHALL NOT store full email bodies. After classification: retain only metadata, classification result, and 500-char excerpt                                                          │
 ├──────────┼─────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────┤
 │ NFR-02.2 │ Full email bodies fetched on-demand from Gmail API, never cached                                                                                                                    │
 ├──────────┼─────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────┤
 │ NFR-02.3 │ PII redacted before LLM transmission: phone numbers -> [PHONE], SSN/CC -> [REDACTED], email signatures stripped. Email addresses/names NOT redacted (needed for contact resolution) │
 ├──────────┼─────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────┤
 │ NFR-02.4 │ Data retention: recommendations 12mo then anonymize, audit logs 24mo then archive, email metadata 6mo then delete, LLM logs 30 days then delete                                     │
 ├──────────┼─────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────┤
 │ NFR-02.5 │ GDPR: support right-to-deletion workflow (purge all records for a contact within 30 days), disclose LLM processing in privacy policy, document lawful basis (legitimate interest)   │
 └──────────┴─────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────┘
 NFR-03: Scalability
 ┌──────────┬──────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────┐
 │    ID    │                                                                                             Requirement                                                                                              │
 ├──────────┼──────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────┤
 │ NFR-03.1 │ Pilot: single instance for 10-20 users. Design SHALL NOT preclude horizontal scaling to 500+                                                                                                         │
 ├──────────┼──────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────┤
 │ NFR-03.2 │ Pilot load: ~500-1,000 emails/day, ~42/hour average, ~100/hour peak. ~2,000-5,000 HubSpot API calls/day                                                                                              │
 ├──────────┼──────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────┤
 │ NFR-03.3 │ For 500+ users: Pub/Sub consumer supports multiple instances, LLM batching for > 1,000 classifications/hour, HubSpot rate limit becomes hard constraint (mitigate with priority queuing and caching) │
 └──────────┴──────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────┘
 NFR-04: Reliability
 ┌──────────┬──────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────┐
 │    ID    │                                                                             Requirement                                                                              │
 ├──────────┼──────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────┤
 │ NFR-04.1 │ Target SLA: 99.5% availability (~3.6 hours downtime/month)                                                                                                           │
 ├──────────┼──────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────┤
 │ NFR-04.2 │ No email silently lost. Pub/Sub acked only after persistence. Duplicates handled via idempotency keys                                                                │
 ├──────────┼──────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────┤
 │ NFR-04.3 │ Circuit breakers for all external deps: Gmail (open after 5 consecutive failures), HubSpot (same), LLM (open after 3), Slack (same as Gmail). Half-open after 30-60s │
 ├──────────┼──────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────┤
 │ NFR-04.4 │ When circuit breaker open, queue messages (Redis/DLQ). Max queue depth 10,000, overflow to PostgreSQL dead_messages table                                            │
 ├──────────┼──────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────┤
 │ NFR-04.5 │ Health check every 30s: DB, Redis, Gmail API, HubSpot API reachability                                                                                               │
 └──────────┴──────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────┘
 NFR-05: Latency
 ┌──────────┬───────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────┐
 │    ID    │                                                                                                    Requirement                                                                                                    │
 ├──────────┼───────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────┤
 │ NFR-05.1 │ Email-to-Slack-notification: p50 < 60s, p95 < 120s, p99 < 300s                                                                                                                                                    │
 ├──────────┼───────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────┤
 │ NFR-05.2 │ Component budgets: Pub/Sub delivery < 2s(p50)/5s(p95), Gmail fetch < 3s/8s, Contact resolution < 2s cached/5s uncached, LLM classification < 5s/15s, Recommendation persist < 100ms/500ms, Slack delivery < 2s/5s │
 ├──────────┼───────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────┤
 │ NFR-05.3 │ Approval-to-CRM-write: p50 < 3s, p95 < 10s                                                                                                                                                                        │
 └──────────┴───────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────┘
 NFR-06: Auditability
 ┌──────────┬───────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────┐
 │    ID    │                                                                                                        Requirement                                                                                                        │
 ├──────────┼───────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────┤
 │ NFR-06.1 │ Every state transition recorded in audit_logs: action, entity_type, entity_id, actor, before_state, after_state, timestamp, trace_id                                                                                      │
 ├──────────┼───────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────┤
 │ NFR-06.2 │ Audited actions: email processed, thread linked, intent classified, recommendation generated/approved/rejected/expired/superseded, CRM write success/failure, config changed, user added/removed, token refreshed/revoked │
 ├──────────┼───────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────┤
 │ NFR-06.3 │ Audit logs immutable: INSERT and SELECT only (enforced via DB role)                                                                                                                                                       │
 ├──────────┼───────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────┤
 │ NFR-06.4 │ API endpoint GET /api/audit/trail/{entity_type}/{entity_id} for full decision chain reconstruction                                                                                                                        │
 └──────────┴───────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────┘
 NFR-07: Explainability
 ┌──────────┬─────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────┐
 │    ID    │                                                                         Requirement                                                                         │
 ├──────────┼─────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────┤
 │ NFR-07.1 │ Every recommendation SHALL include: intent detected, key phrases, confidence with qualitative label (High/Medium/Low), mapping rule applied                 │
 ├──────────┼─────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────┤
 │ NFR-07.2 │ Dashboard "Decision Trail" view: triggering email (subject + excerpt) -> LLM classification -> stage mapping -> recommendation -> user action -> CRM result │
 ├──────────┼─────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────┤
 │ NFR-07.3 │ Rejected recommendations queryable by rejection reason for systematic error identification                                                                  │
 └──────────┴─────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────┘
 NFR-08: Maintainability
 ┌──────────┬────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────┐
 │    ID    │                                                                                          Requirement                                                                                           │
 ├──────────┼────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────┤
 │ NFR-08.1 │ Modular architecture: ingestion, classification, recommendation, notification, CRM update as distinct modules with defined interfaces. Single process for pilot, extractable to services later │
 ├──────────┼────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────┤
 │ NFR-08.2 │ All integrations (Gmail, HubSpot, Slack, LLM) abstracted behind interfaces (Python ABCs/Protocols) for provider swapping                                                                       │
 ├──────────┼────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────┤
 │ NFR-08.3 │ Config hierarchy: env vars (infra) -> DB config (runtime) -> hardcoded defaults. DB overrides env for business rules                                                                           │
 ├──────────┼────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────┤
 │ NFR-08.4 │ Test suite: unit tests > 80% coverage, integration tests per API (mocked), E2E tests with HubSpot sandbox                                                                                      │
 ├──────────┼────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────┤
 │ NFR-08.5 │ DB migrations via Alembic with forward-only in production, reversible in dev                                                                                                                   │
 └──────────┴────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────┘
 ---
 8. System Architecture

 8.1 Component Breakdown
 ┌───────────────────────┬────────────────────────────────────────────────────────────────┬──────────────────────────────────────────┐
 │       Component       │                         Responsibility                         │                Tech Stack                │
 ├───────────────────────┼────────────────────────────────────────────────────────────────┼──────────────────────────────────────────┤
 │ Pub/Sub Consumer      │ Pull messages from GCP Pub/Sub, deduplicate, dispatch          │ Python, google-cloud-pubsub              │
 ├───────────────────────┼────────────────────────────────────────────────────────────────┼──────────────────────────────────────────┤
 │ Ingestion Service     │ Fetch email from Gmail API, persist metadata, trigger linking  │ Python/FastAPI, google-api-python-client │
 ├───────────────────────┼────────────────────────────────────────────────────────────────┼──────────────────────────────────────────┤
 │ Thread Linker         │ Resolve emails -> HubSpot contacts -> deals, maintain mappings │ Python, hubspot-api-client, Redis        │
 ├───────────────────────┼────────────────────────────────────────────────────────────────┼──────────────────────────────────────────┤
 │ Intent Analyzer       │ LLM prompt construction, API call, response parsing            │ Python, anthropic SDK / openai SDK       │
 ├───────────────────────┼────────────────────────────────────────────────────────────────┼──────────────────────────────────────────┤
 │ Stage Mapper          │ Map intent -> HubSpot stage, validate transitions              │ Python, config-driven                    │
 ├───────────────────────┼────────────────────────────────────────────────────────────────┼──────────────────────────────────────────┤
 │ Recommendation Engine │ Apply thresholds, deduplicate, generate recommendations        │ Python, PostgreSQL                       │
 ├───────────────────────┼────────────────────────────────────────────────────────────────┼──────────────────────────────────────────┤
 │ Notification Service  │ Slack Block Kit messages, interaction callbacks                │ Python/FastAPI, slack-sdk                │
 ├───────────────────────┼────────────────────────────────────────────────────────────────┼──────────────────────────────────────────┤
 │ CRM Updater           │ HubSpot deal writes, conflict detection, idempotency           │ Python, hubspot-api-client, Redis        │
 ├───────────────────────┼────────────────────────────────────────────────────────────────┼──────────────────────────────────────────┤
 │ Web Dashboard         │ Admin UI, approval interface, analytics                        │ Next.js 14, TypeScript, Tailwind         │
 ├───────────────────────┼────────────────────────────────────────────────────────────────┼──────────────────────────────────────────┤
 │ API Gateway           │ REST API, auth, RBAC                                           │ Python/FastAPI, OIDC middleware          │
 ├───────────────────────┼────────────────────────────────────────────────────────────────┼──────────────────────────────────────────┤
 │ Background Workers    │ Watch renewal, DLQ, expiration, token refresh                  │ Python, APScheduler                      │
 ├───────────────────────┼────────────────────────────────────────────────────────────────┼──────────────────────────────────────────┤
 │ Database              │ Persistent storage                                             │ PostgreSQL 15+                           │
 ├───────────────────────┼────────────────────────────────────────────────────────────────┼──────────────────────────────────────────┤
 │ Cache / Rate Limiter  │ Contact cache, rate limiting, DLQ                              │ Redis 7+                                 │
 └───────────────────────┴────────────────────────────────────────────────────────────────┴──────────────────────────────────────────┘
 8.2 Architecture Diagram

                                     EXTERNAL SERVICES
                     +-----------+  +------------+  +-----------+
                     | Gmail API |  | HubSpot API|  | Claude API|
                     +-----+-----+  +------+-----+  +-----+-----+
                           |               |               |
                           v               |               |
                  +--------+--------+      |               |
                  | GCP Pub/Sub     |      |               |
                  | Topic: gmail-   |      |               |
                  | push-notifs     |      |               |
                  +--------+--------+      |               |
                           |               |               |
     ===================== | ============= | ============= | ===========
     SYSTEM BOUNDARY       |               |               |
                           v               |               |
                  +--------+--------+      |               |
                  | Pub/Sub Consumer|      |               |
                  | (Pull Worker)   |      |               |
                  +--------+--------+      |               |
                           |               |               |
                           v               |               |
                  +--------+--------+      |               |
                  | Ingestion       +------+               |
                  | Service         | (Gmail API)          |
                  +--------+--------+                      |
                           |                               |
                           v                               |
                  +--------+--------+      +----------+    |
                  | Thread Linker   +----->| Redis    |    |
                  | (Contact/Deal   |<-----| Cache    |    |
                  |  Resolution)    |      +----------+    |
                  +--------+--------+                      |
                           | (HubSpot API)                 |
                           v                               |
                  +--------+--------+                      |
                  | Intent Analyzer +----------------------+
                  | (LLM Client)    | (email -> LLM)
                  +--------+--------+
                           |
                           v
                  +--------+--------+
                  | Stage Mapper    |
                  +--------+--------+
                           |
                           v
                  +--------+-----------+
                  | Recommendation     |
                  | Engine             |
                  +--------+-----------+
                           |
                +----------+----------+
                |                     |
                v                     v
       +--------+--------+  +--------+--------+
       | Slack Notifier  |  | Web Dashboard   |
       | (Block Kit)     |  | (Next.js)       |
       +--------+--------+  +--------+--------+
                |                     |
                v                     v
       +--------+--------+  +--------+--------+
       | Slack Interaction|  | API Gateway     |
       | Webhook Handler |  | (FastAPI)       |
       +--------+--------+  +--------+--------+
                |                     |
                +----------+----------+
                           |
                           v
                  +--------+--------+
                  | CRM Updater    +-------> HubSpot API
                  +--------+--------+
                           |
                           v
                  +--------+--------+     +-------------+
                  | PostgreSQL      +---->| Audit Log   |
                  | (All entities)  |     | (Immutable) |
                  +-----------------+     +-------------+

     BACKGROUND WORKERS (Scheduled):
     +-------------------+  +-------------------+  +-------------------+
     | Watch Renewal     |  | DLQ Processor     |  | Token Refresh     |
     | (daily 02:00 UTC) |  | (every 15 min)    |  | (every 30 min)    |
     +-------------------+  +-------------------+  +-------------------+
     +-------------------+  +-------------------+
     | Recommendation    |  | Pipeline Config   |
     | Expiration (1h)   |  | Sync (every 6h)   |
     +-------------------+  +-------------------+

 8.3 Retry Strategy

 All retries follow exponential backoff with jitter:

 delay = min(base_delay * (2 ^ attempt) + random_jitter(0, 1s), max_delay)

 Default:    base=1s, max=60s, retries=4
 LLM:        base=2s, max=30s, retries=3
 HubSpot:    base=1s, max=30s, retries=4 (+ Retry-After header)

 8.4 Dead Letter Queue

 - Storage: Redis list dlq:{component_name} with JSON payloads
 - Each entry: { id, original_message, component, error, retry_count, first_failed_at, last_failed_at, trace_id }
 - DLQ Processor runs every 15 minutes, processes up to 50 messages
 - Messages with retry_count > 10 -> PostgreSQL dead_messages table + alert

 ---
 9. Data Model

 9.1 Core Entities

 email_messages: Gmail message metadata (no full body stored)
 - id (UUID PK), gmail_message_id (UNIQUE), gmail_thread_id, gmail_history_id, user_id (FK), from_address, to_addresses (TEXT[]), cc_addresses (TEXT[]), subject, body_excerpt (VARCHAR 500), received_at, processed_at, processing_status, trace_id

 email_threads: Gmail thread -> HubSpot deal mapping
 - id (UUID PK), gmail_thread_id (UNIQUE), deal_id (FK), contact_ids (UUID[]), subject, message_count, last_activity_at, link_confidence, link_method

 deals: Cached HubSpot deal data
 - id (UUID PK), hubspot_deal_id (UNIQUE), pipeline_id (FK), hubspot_pipeline_id, current_stage, current_stage_name, deal_name, owner_user_id (FK), contact_ids (UUID[]), amount, close_date, last_synced_at

 stage_recommendations: Core recommendation entity with state machine
 - id (UUID PK), email_message_id (FK), thread_id (FK), deal_id (FK), current_stage, recommended_stage, recommended_stage_name, confidence_score (DECIMAL 4,3), intent, reasoning, key_phrases (TEXT[]), direction, prompt_version, llm_model,
 llm_latency_ms, status (pending/approved/rejected/expired/superseded/conflict/write_failed), reviewed_at, reviewed_by (FK), rejection_reason, user_corrected_stage, slack_message_ts, slack_channel_id, snooze_count, expires_at, idempotency_key
 (UNIQUE)

 audit_logs: Immutable audit trail (INSERT + SELECT only)
 - id (UUID PK), trace_id, action, entity_type, entity_id, actor_type (system/user), actor_id, before_state (JSONB), after_state (JSONB), metadata (JSONB), timestamp

 user_configs: User profiles and integration state
 - id (UUID PK), email (UNIQUE), display_name, role (admin/revops/sales_user), hubspot_user_id, hubspot_owner_id, slack_user_id, gmail_watch_expiration, gmail_last_history_id, notification_channel, is_active

 credentials: Encrypted OAuth tokens
 - id (UUID PK), user_id (FK), provider (gmail/hubspot/slack), access_token_enc (BYTEA, AES-256), refresh_token_enc (BYTEA), token_expiry, scopes (TEXT[]), UNIQUE(user_id, provider)

 pipeline_configs: HubSpot pipeline mappings
 - id (UUID PK), hubspot_pipeline_id (UNIQUE), pipeline_name, stages (JSONB), intent_to_stage_rules (JSONB), stage_ordering (JSONB), is_active, recommendation_threshold, logging_threshold, approval_timeout_hours, max_snoozes

 prompt_versions: Versioned LLM prompts
 - id (UUID PK), version (UNIQUE), prompt_template, system_prompt, intent_categories (JSONB), is_active (only one active), created_by (FK), notes

 intent_classifications: All classifications (for analytics/training)
 - id (UUID PK), email_message_id (FK), deal_id (FK), intent, confidence_score, reasoning, key_phrases (TEXT[]), direction, prompt_version, llm_model, llm_latency_ms, input_tokens, output_tokens, action_taken

 dead_messages: DLQ overflow
 - id (UUID PK), component, original_payload (JSONB), error_message, retry_count, trace_id, first_failed_at, last_failed_at, resolved, resolved_at, resolved_by (FK)

 9.2 Entity Relationships

 user_configs 1---* email_messages       (user owns emails)
 user_configs 1---* credentials          (per provider)
 user_configs 1---* deals                (as HubSpot owner)
 email_messages *---1 email_threads      (many emails per thread)
 email_threads  *---1 deals              (many threads per deal)
 deals *---1 pipeline_configs            (deal belongs to pipeline)
 stage_recommendations *---1 email_messages  (triggered by email)
 stage_recommendations *---1 email_threads   (within thread)
 stage_recommendations *---1 deals           (for deal)
 intent_classifications *---1 email_messages (one per email)
 audit_logs: polymorphic via entity_type + entity_id (no FK)

 ---
 10. Dependencies

 10.1 Gmail API

 - Endpoints: users.watch, users.stop, users.history.list, users.messages.get, users.messages.list, users.getProfile
 - OAuth Scope: https://www.googleapis.com/auth/gmail.readonly (restricted scope -- requires Google security review for > 100 users; pilot stays in "testing" mode)
 - Rate Limits: 250 quota units/user/sec. messages.get = 5 units. Effective: ~50 messages/sec/user

 10.2 Google Cloud Pub/Sub

 - Setup: Topic + pull subscription. Grant gmail-api-push@system.gserviceaccount.com Publisher role
 - Message Format: Base64 JSON: { "emailAddress": "...", "historyId": 12345 }
 - Delivery: At-least-once. Application handles duplicates
 - Cost: First 10GB/month free. Pilot: negligible

 10.3 HubSpot API (v3)

 - Endpoints: GET/PATCH /crm/v3/objects/deals/{id}, POST /crm/v3/objects/deals/search, GET /crm/v3/objects/contacts/search, GET /crm/v4/objects/contacts/{id}/associations/deals, GET /crm/v3/pipelines/deals, POST /crm/v3/objects/notes
 - OAuth Scopes: crm.objects.deals.read, crm.objects.deals.write, crm.objects.contacts.read, crm.schemas.deals.read, crm.objects.owners.read
 - Rate Limits: 110 req/10s (OAuth public apps), 190 req/10s (private apps), 250K req/day
 - Recommendation: Use private app token for pilot (simpler, higher rate limit)

 10.4 LLM Provider

 - Primary: Anthropic Claude Haiku 4.5 (~$0.0025/classification)
 - Secondary: OpenAI GPT-4o-mini (fallback)
 - Pilot cost: ~$75/month at 1,000 emails/day
 - Rate Limits: ~60 RPM for Haiku Tier 1 (sufficient for ~42/hour peak)
 - Latency: p50 ~1-2s, p95 ~4-5s

 10.5 Slack API

 - APIs: chat.postMessage, chat.update, users.lookupByEmail, interaction webhook
 - Bot Scopes: chat:write, chat:write.public, users:read, users:read.email
 - Rate Limits: ~20 req/min for chat.postMessage (sufficient for pilot)

 10.6 Infrastructure

 - PostgreSQL 15+: Google Cloud SQL or managed. < 1GB for 6 months
 - Redis 7+: Google Cloud Memorystore. < 100MB
 - Compute: Single Cloud Run service for pilot. Estimated: < $50/month total

 ---
 11. Risks & Mitigations
 ┌─────┬───────────────────────────┬──────────────┬────────┬─────────────────────────────────────────────────────────────────────────────────────────────────────────────┬───────────────────────────────────────────────────────────────┐
 │  #  │           Risk            │  Likelihood  │ Impact │                                                 Mitigation                                                  │                         Residual Risk                         │
 ├─────┼───────────────────────────┼──────────────┼────────┼─────────────────────────────────────────────────────────────────────────────────────────────────────────────┼───────────────────────────────────────────────────────────────┤
 │ R1  │ AI Misclassification      │ High->Medium │ Medium │ Confidence thresholds (0.70 min), human review for ALL, rejection feedback loop, prompt versioning          │ Approval fatigue risk. Mitigate with periodic accuracy audits │
 ├─────┼───────────────────────────┼──────────────┼────────┼─────────────────────────────────────────────────────────────────────────────────────────────────────────────┼───────────────────────────────────────────────────────────────┤
 │ R2  │ User Trust Erosion        │ Medium       │ High   │ Soft launch with 3-5 engaged reps, tune prompts on real data, transparent confidence scores, easy rejection │ Some users may never adopt. 70%+ is success                   │
 ├─────┼───────────────────────────┼──────────────┼────────┼─────────────────────────────────────────────────────────────────────────────────────────────────────────────┼───────────────────────────────────────────────────────────────┤
 │ R3  │ HubSpot API Rate Limits   │ Low (pilot)  │ Medium │ Redis token bucket, priority queue (writes > reads), response caching (1h TTL)                              │ At 500+ users, may need capacity pack                         │
 ├─────┼───────────────────────────┼──────────────┼────────┼─────────────────────────────────────────────────────────────────────────────────────────────────────────────┼───────────────────────────────────────────────────────────────┤
 │ R4  │ Privacy / Compliance      │ Medium       │ High   │ PII redaction, no body storage, retention policies, GDPR deletion, LLM provider DPA                         │ Residual: LLM provider data handling. Use zero-retention API  │
 ├─────┼───────────────────────────┼──────────────┼────────┼─────────────────────────────────────────────────────────────────────────────────────────────────────────────┼───────────────────────────────────────────────────────────────┤
 │ R5  │ Gmail Watch Expiration    │ Medium       │ High   │ Daily renewal cron (not day 7), alert on failure, "no emails in 24h" detection                              │ Transient GCP outages. Multiple retries reduce risk           │
 ├─────┼───────────────────────────┼──────────────┼────────┼─────────────────────────────────────────────────────────────────────────────────────────────────────────────┼───────────────────────────────────────────────────────────────┤
 │ R6  │ HubSpot Conflicts         │ Medium       │ Low    │ Read-before-write, conflict notification, never silently overwrite                                          │ Small race window. Acceptable at pilot scale                  │
 ├─────┼───────────────────────────┼──────────────┼────────┼─────────────────────────────────────────────────────────────────────────────────────────────────────────────┼───────────────────────────────────────────────────────────────┤
 │ R7  │ LLM Cost Overrun          │ Low          │ Low    │ Haiku (cheapest), token cap (4,096), monthly alerting ($100 threshold)                                      │ Worst case ~$150/month. Acceptable                            │
 ├─────┼───────────────────────────┼──────────────┼────────┼─────────────────────────────────────────────────────────────────────────────────────────────────────────────┼───────────────────────────────────────────────────────────────┤
 │ R8  │ Single Point of Failure   │ Medium       │ Medium │ At-least-once Pub/Sub, DLQ, circuit breakers, Cloud Run auto-restart                                        │ ~30-60s gaps during restarts. Pub/Sub buffers                 │
 ├─────┼───────────────────────────┼──────────────┼────────┼─────────────────────────────────────────────────────────────────────────────────────────────────────────────┼───────────────────────────────────────────────────────────────┤
 │ R9  │ Email Threading Errors    │ Low-Medium   │ Medium │ Allow manual thread-deal override, validate participant coherence, surface multi-deal matches               │ Human review catches in approval step                         │
 ├─────┼───────────────────────────┼──────────────┼────────┼─────────────────────────────────────────────────────────────────────────────────────────────────────────────┼───────────────────────────────────────────────────────────────┤
 │ R10 │ Slack Adoption Dependency │ Medium       │ Medium │ Web dashboard alternative, email digest fallback, snooze, configurable notification channel                 │ Expiration acceptable vs stale CRM                            │
 └─────┴───────────────────────────┴──────────────┴────────┴─────────────────────────────────────────────────────────────────────────────────────────────────────────────┴───────────────────────────────────────────────────────────────┘
 ---
 12. Success Metrics

 12.1 Primary KPIs (Weekly, 12-Week Pilot)
 ┌─────────────────────────────────────────────┬─────────────────┬──────────────────┬───────────────────────────────────────────────┐
 │                   Metric                    │ Target (Week 4) │ Target (Week 12) │                  Measurement                  │
 ├─────────────────────────────────────────────┼─────────────────┼──────────────────┼───────────────────────────────────────────────┤
 │ Adoption Rate (% users active/week)         │ > 60%           │ > 80%            │ Distinct reviewed_by per week                 │
 ├─────────────────────────────────────────────┼─────────────────┼──────────────────┼───────────────────────────────────────────────┤
 │ Recommendation Accuracy (approved/reviewed) │ > 65%           │ > 80%            │ approved / (approved + rejected)              │
 ├─────────────────────────────────────────────┼─────────────────┼──────────────────┼───────────────────────────────────────────────┤
 │ Email-to-Notification Latency p50           │ < 90s           │ < 60s            │ recommendation.created_at - email.received_at │
 ├─────────────────────────────────────────────┼─────────────────┼──────────────────┼───────────────────────────────────────────────┤
 │ Email-to-Notification Latency p95           │ < 300s          │ < 120s           │ Same, 95th percentile                         │
 ├─────────────────────────────────────────────┼─────────────────┼──────────────────┼───────────────────────────────────────────────┤
 │ CRM Update Frequency (vs baseline)          │ +50%            │ +100%            │ HubSpot stage change events pre/post          │
 ├─────────────────────────────────────────────┼─────────────────┼──────────────────┼───────────────────────────────────────────────┤
 │ Deal Coverage (% deals with linked threads) │ > 50%           │ > 75%            │ Deals with threads / active deals             │
 └─────────────────────────────────────────────┴─────────────────┴──────────────────┴───────────────────────────────────────────────┘
 12.2 Secondary KPIs
 ┌─────────────────────────────────────────────┬────────────────┐
 │                   Metric                    │     Target     │
 ├─────────────────────────────────────────────┼────────────────┤
 │ Classification Coverage (classified/linked) │ > 95%          │
 ├─────────────────────────────────────────────┼────────────────┤
 │ Expiration Rate                             │ < 25%          │
 ├─────────────────────────────────────────────┼────────────────┤
 │ System Uptime                               │ > 99.5%        │
 ├─────────────────────────────────────────────┼────────────────┤
 │ LLM Cost per Classification                 │ < $0.005       │
 ├─────────────────────────────────────────────┼────────────────┤
 │ User Satisfaction (NPS at week 12)          │ > 50           │
 ├─────────────────────────────────────────────┼────────────────┤
 │ RevOps Time Saved (self-reported)           │ > 4 hours/week │
 └─────────────────────────────────────────────┴────────────────┘
 12.3 Anti-Metrics
 ┌─────────────────────────────────────────────────────┬────────────────────────────────────────┬────────┐
 │                     Anti-Metric                     │               Threshold                │ Action │
 ├─────────────────────────────────────────────────────┼────────────────────────────────────────┼────────┤
 │ Rubber-stamping (> 95% approval sustained 2+ weeks) │ Investigate, add decoy recommendations │        │
 ├─────────────────────────────────────────────────────┼────────────────────────────────────────┼────────┤
 │ Over-notification (> 10 recs/user/day)              │ Raise threshold or batch notifications │        │
 ├─────────────────────────────────────────────────────┼────────────────────────────────────────┼────────┤
 │ Silent failures (any email lost without trace)      │ Incident review, improve DLQ           │        │
 └─────────────────────────────────────────────────────┴────────────────────────────────────────┴────────┘
 ---
 13. Roadmap Outlook

 Phase 1: Human-in-the-Loop Pilot (Current -- Weeks 1-12)

 Gmail push ingestion, thread linking, LLM classification, Slack approval, HubSpot writeback, full audit trail.

 Exit Criteria for Phase 2: Accuracy > 80%, adoption > 80%, no critical failures for 4 weeks, NPS > 40.

 Phase 2: Autonomous Mode (Months 4-6)

 - AUTO_APPROVE_THRESHOLD (e.g., 0.95) for high-confidence auto-apply
 - Undo functionality (1-hour window)
 - A/B testing framework
 - Expansion to 50-100 users

 Phase 3: Multi-CRM and Multi-Email (Months 7-12)

 - CRM abstraction layer: Salesforce, Pipedrive adapters
 - Email provider abstraction: Microsoft Graph (Outlook)
 - Multi-tenant architecture (if externalizing)
 - Webhook-based bidirectional CRM sync

 Phase 4: Agent Orchestration (Months 12-18)

 - Deal risk scoring
 - Next-best-action recommendations
 - Meeting intelligence integration
 - Multi-signal fusion (email + calls + CRM + web analytics)
 - Agent framework for autonomous follow-ups
 - Revenue forecasting

 ---
 Appendices

 Appendix A: LLM Prompt Template (v1.0 Reference)

 SYSTEM PROMPT:
 You are a sales deal stage analyst. Your job is to read a sales email and
 determine what it signals about the progression of a B2B sales deal.

 Classify the email into exactly ONE intent category from the provided list.

 Respond ONLY with valid JSON:
 {
   "intent": "<intent_category>",
   "confidence": <float 0.0-1.0>,
   "reasoning": "<2-3 sentences>",
   "key_phrases": ["<phrase1>", "<phrase2>"],
   "direction": "<forward|backward|neutral>"
 }

 Rules:
 - Use 0.9+ confidence only when signal is unambiguous
 - Consider current deal stage. Do not classify as earlier stage unless
   explicit regression signal exists
 - "no_deal_signal" for non-deal emails (scheduling, OOO, etc.)

 USER PROMPT:
 ## Current Deal Context
 - Deal Name: {deal_name}
 - Current Stage: {current_stage_name}
 - Pipeline: {pipeline_name}

 ## Thread History (last 2-3 emails)
 {thread_history}

 ## Email to Analyze
 From: {from_address} | To: {to_addresses} | CC: {cc_addresses}
 Subject: {subject} | Date: {received_at}

 --- EMAIL BODY ---
 {body_text}
 --- END ---

 Classify this email.

 Appendix B: Suggested Project Structure

 hubspot-pipeline-intelligence/
 ├── backend/
 │   ├── app/
 │   │   ├── main.py                     # FastAPI entry point
 │   │   ├── config.py                   # Configuration
 │   │   ├── dependencies.py             # DI container
 │   │   ├── api/routes/                 # REST endpoints
 │   │   │   ├── recommendations.py
 │   │   │   ├── deals.py
 │   │   │   ├── admin.py
 │   │   │   ├── auth.py
 │   │   │   ├── slack_interactions.py
 │   │   │   └── health.py
 │   │   ├── api/middleware/             # Auth, RBAC, logging
 │   │   ├── services/                   # Business logic
 │   │   │   ├── ingestion.py
 │   │   │   ├── thread_linker.py
 │   │   │   ├── intent_analyzer.py
 │   │   │   ├── stage_mapper.py
 │   │   │   ├── recommendation.py
 │   │   │   ├── notification.py
 │   │   │   ├── crm_updater.py
 │   │   │   └── audit.py
 │   │   ├── integrations/               # External API clients
 │   │   │   ├── gmail/client.py
 │   │   │   ├── hubspot/client.py
 │   │   │   ├── llm/base.py            # Abstract interface
 │   │   │   ├── llm/anthropic.py
 │   │   │   ├── llm/openai.py
 │   │   │   └── slack/client.py
 │   │   ├── models/                     # SQLAlchemy ORM
 │   │   ├── workers/                    # Background jobs
 │   │   │   ├── pubsub_consumer.py
 │   │   │   ├── watch_renewer.py
 │   │   │   ├── dlq_processor.py
 │   │   │   ├── token_refresher.py
 │   │   │   ├── expiration_worker.py
 │   │   │   └── pipeline_sync.py
 │   │   └── utils/                      # Shared utilities
 │   │       ├── encryption.py
 │   │       ├── pii_redactor.py
 │   │       ├── rate_limiter.py
 │   │       ├── circuit_breaker.py
 │   │       └── retry.py
 │   ├── alembic/                        # DB migrations
 │   ├── tests/
 │   ├── pyproject.toml
 │   └── Dockerfile
 ├── dashboard/                          # Next.js web UI
 │   ├── src/app/
 │   │   ├── dashboard/
 │   │   │   ├── recommendations/
 │   │   │   ├── deals/
 │   │   │   ├── analytics/
 │   │   │   └── admin/
 │   │   └── (auth)/
 │   └── package.json
 ├── infra/
 │   ├── terraform/
 │   └── docker-compose.yml
 ├── docs/
 │   ├── architecture.md
 │   ├── runbook.md
 │   └── api-spec.yaml
 └── .github/workflows/

 Appendix C: Critical Files for Implementation
 ┌──────────────────────────────────────────────┬───────────────────────────────────────────────────────────────────────────────────────────────┐
 │                     File                     │                                        Why It Matters                                         │
 ├──────────────────────────────────────────────┼───────────────────────────────────────────────────────────────────────────────────────────────┤
 │ backend/app/services/intent_analyzer.py      │ Core LLM classification orchestration -- most complex business logic, primary differentiator  │
 ├──────────────────────────────────────────────┼───────────────────────────────────────────────────────────────────────────────────────────────┤
 │ backend/app/workers/pubsub_consumer.py       │ Pipeline entry point. Message loss = missed emails. Must be reliable                          │
 ├──────────────────────────────────────────────┼───────────────────────────────────────────────────────────────────────────────────────────────┤
 │ backend/app/integrations/hubspot/client.py   │ HubSpot abstraction: deal reads/writes, contact resolution, rate limiting, conflict detection │
 ├──────────────────────────────────────────────┼───────────────────────────────────────────────────────────────────────────────────────────────┤
 │ backend/app/api/routes/slack_interactions.py │ Primary user interaction surface. Signature validation, payload parsing, CRM orchestration    │
 ├──────────────────────────────────────────────┼───────────────────────────────────────────────────────────────────────────────────────────────┤
 │ backend/app/models/stage_recommendation.py   │ Central entity. State machine drives entire approval workflow                                 │
 └──────────────────────────────────────────────┴───────────────────────────────────────────────────────────────────────────────────────────────┘
 ---
 Verification Plan

 1. Unit Tests: Run pytest --cov=src --cov-report=term-missing -v -- target > 80% coverage on business logic
 2. Integration Tests: Mock external APIs (Gmail, HubSpot, Claude, Slack) and verify end-to-end flow
 3. E2E Test: Use HubSpot sandbox account + Gmail test account to verify complete pipeline
 4. Manual Smoke Test: Send a real email, observe Pub/Sub notification, verify Slack recommendation appears, approve, confirm HubSpot deal stage updated
 5. Observability Check: Verify trace_id propagates from Pub/Sub message through to audit log
 6. Failure Injection: Simulate LLM timeout, HubSpot 429, Slack delivery failure -- verify DLQ and alerts function correctly