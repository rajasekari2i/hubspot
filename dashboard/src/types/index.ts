// ──────────────────────────────────────────────────────────────
// Shared TypeScript types matching the backend API schemas
// See: specs/001-pipeline-intelligence/contracts/api.yaml
// ──────────────────────────────────────────────────────────────

// ── Enums / Literal Unions ───────────────────────────────────

export type RecommendationStatus =
  | 'pending'
  | 'approved'
  | 'rejected'
  | 'expired'
  | 'superseded'
  | 'conflict'
  | 'write_failed'
  | 'snoozed';

export type Direction = 'forward' | 'backward' | 'neutral';

export type ConfidenceLabel = 'high' | 'medium' | 'low';

export type UserRole = 'admin' | 'revops' | 'sales_user';

export type RejectionReason = 'wrong_stage' | 'wrong_deal' | 'not_relevant' | 'other';

export type ActorType = 'system' | 'user';

export type HealthStatusLevel = 'healthy' | 'degraded' | 'unhealthy';

export type HealthCheckStatus = 'ok' | 'degraded' | 'down';

export type CrmResultStatus = 'success' | 'failed' | 'conflict' | 'pending';

export type UserActionType = 'approved' | 'rejected' | 'expired' | 'superseded';

export type BulkAction = 'approve' | 'reject';

export type SortField = 'created_at' | 'confidence_score' | 'expires_at';

export type SortOrder = 'asc' | 'desc';

// ── Core Entities ────────────────────────────────────────────

export interface Recommendation {
  id: string;
  deal_id: string;
  deal_name: string;
  current_stage: string;
  current_stage_name: string;
  recommended_stage: string;
  recommended_stage_name: string;
  confidence_score: number;
  confidence_label: ConfidenceLabel;
  intent: string;
  reasoning: string;
  key_phrases: string[];
  direction: Direction;
  status: RecommendationStatus;
  reviewed_by: string | null;
  reviewed_at: string | null;
  rejection_reason: RejectionReason | null;
  user_corrected_stage: string | null;
  snooze_count: number;
  expires_at: string;
  created_at: string;
  email_subject: string;
  email_excerpt: string;
  hubspot_deal_url: string;
  gmail_thread_url: string | null;
}

export interface RecommendationList {
  items: Recommendation[];
  total: number;
  page: number;
  page_size: number;
}

export interface DealOwner {
  id: string;
  display_name: string;
  email: string;
}

export interface Deal {
  id: string;
  hubspot_deal_id: string;
  deal_name: string;
  current_stage: string;
  current_stage_name: string;
  pipeline_name: string;
  owner: DealOwner;
  amount: number | null;
  close_date: string | null;
  thread_count: number;
  recommendation_count: number;
  last_synced_at: string;
}

// ── Decision Trail ───────────────────────────────────────────

export interface DecisionTrailEmail {
  subject: string;
  excerpt: string;
  from_address: string;
  received_at: string;
}

export interface DecisionTrailClassification {
  intent: string;
  confidence_score: number;
  reasoning: string;
  key_phrases: string[];
  direction: string;
  prompt_version: string;
  llm_model: string;
}

export interface DecisionTrailMapping {
  pipeline_name: string;
  current_stage: string;
  recommended_stage: string;
  rule_applied: string;
}

export interface DecisionTrailUserAction {
  action: UserActionType;
  actor: string;
  acted_at: string;
  rejection_reason: string | null;
}

export interface DecisionTrailCrmResult {
  status: CrmResultStatus;
  updated_at: string | null;
  error: string | null;
}

export interface DecisionTrail {
  recommendation_id: string;
  email: DecisionTrailEmail;
  classification: DecisionTrailClassification;
  mapping: DecisionTrailMapping;
  user_action: DecisionTrailUserAction | null;
  crm_result: DecisionTrailCrmResult | null;
}

// ── Analytics ────────────────────────────────────────────────

export interface AnalyticsPeriod {
  start: string;
  end: string;
}

export interface AnalyticsRecommendations {
  total: number;
  approved: number;
  rejected: number;
  expired: number;
  pending: number;
  approval_rate: number;
}

export interface AnalyticsConfidence {
  average: number;
  p50: number;
  p95: number;
}

export interface AnalyticsLatency {
  email_to_notification_p50_seconds: number;
  email_to_notification_p95_seconds: number;
  approval_to_crm_p50_seconds: number;
  approval_to_crm_p95_seconds: number;
}

export interface AnalyticsDealCoverage {
  total_active_deals: number;
  deals_with_threads: number;
  coverage_percent: number;
}

export interface AnalyticsOverview {
  period: AnalyticsPeriod;
  recommendations: AnalyticsRecommendations;
  rejections_by_reason: Record<string, number>;
  confidence: AnalyticsConfidence;
  latency: AnalyticsLatency;
  deal_coverage: AnalyticsDealCoverage;
}

// ── Audit ────────────────────────────────────────────────────

export interface AuditLogEntry {
  id: string;
  trace_id: string | null;
  action: string;
  entity_type: string;
  entity_id: string;
  actor_type: ActorType;
  actor_id: string | null;
  before_state: Record<string, unknown> | null;
  after_state: Record<string, unknown> | null;
  metadata: Record<string, unknown>;
  created_at: string;
}

// ── Admin: Users ─────────────────────────────────────────────

export interface UserConfig {
  id: string;
  email: string;
  display_name: string;
  role: UserRole;
  hubspot_owner_id: string | null;
  slack_user_id: string | null;
  is_active: boolean;
  gmail_watch_active: boolean;
  created_at: string;
}

export interface CreateUserRequest {
  email: string;
  display_name: string;
  role: UserRole;
  hubspot_owner_id?: string | null;
  slack_user_id?: string | null;
}

export interface UpdateUserRequest {
  display_name?: string;
  role?: UserRole;
  hubspot_owner_id?: string;
  slack_user_id?: string;
  is_active?: boolean;
}

// ── Admin: Pipelines ─────────────────────────────────────────

export interface PipelineStage {
  id: string;
  name: string;
  order: number;
}

export interface PipelineConfig {
  id: string;
  hubspot_pipeline_id: string;
  pipeline_name: string;
  stages: PipelineStage[];
  intent_to_stage_rules: Record<string, string>;
  is_active: boolean;
  recommendation_threshold: number;
  logging_threshold: number;
  approval_timeout_hours: number;
  max_snoozes: number;
}

export interface UpdatePipelineConfigRequest {
  intent_to_stage_rules?: Record<string, string>;
  recommendation_threshold?: number;
  logging_threshold?: number;
  approval_timeout_hours?: number;
  max_snoozes?: number;
  is_active?: boolean;
}

// ── Admin: Prompts ───────────────────────────────────────────

export interface PromptVersion {
  id: string;
  version: string;
  prompt_template: string;
  system_prompt: string;
  intent_categories: string[];
  is_active: boolean;
  created_by: string | null;
  notes: string | null;
  created_at: string;
}

export interface CreatePromptVersionRequest {
  version: string;
  prompt_template: string;
  system_prompt: string;
  intent_categories: string[];
  notes?: string | null;
}

// ── Health ───────────────────────────────────────────────────

export interface HealthCheck {
  status: HealthCheckStatus;
  latency_ms: number | null;
  last_checked: string;
  error: string | null;
}

export interface HealthChecks {
  database: HealthCheck;
  redis: HealthCheck;
  gmail_api: HealthCheck;
  hubspot_api: HealthCheck;
  llm_api: HealthCheck;
  slack_api: HealthCheck;
}

export interface HealthStatus {
  status: HealthStatusLevel;
  checks: HealthChecks;
  timestamp: string;
}

// ── Requests ─────────────────────────────────────────────────

export interface ApproveRequest {
  // Empty body per API spec; included for type safety
}

export interface RejectRequest {
  reason: RejectionReason;
  corrected_stage?: string | null;
}

export interface SnoozeRequest {
  duration_hours?: number;
}

export interface BulkActionRequest {
  action: BulkAction;
  recommendation_ids: string[];
  rejection_reason?: string;
}

// ── Generic Paginated Response ───────────────────────────────

export interface PaginatedResponse<T> {
  items: T[];
  total: number;
  page?: number;
  page_size?: number;
}

// ── Low-Confidence Classification ────────────────────────────

export interface LowConfidenceClassification {
  id: string;
  email_subject: string;
  email_excerpt: string;
  intent: string;
  confidence_score: number;
  reasoning: string;
  deal_name: string | null;
  created_at: string;
}

// ── API Error ────────────────────────────────────────────────

export interface ApiErrorResponse {
  error: string;
  detail: string;
  trace_id: string;
}

// ── Query Parameter Types ────────────────────────────────────

export interface RecommendationListParams {
  page?: number;
  page_size?: number;
  status?: RecommendationStatus;
  deal_id?: string;
  min_confidence?: number;
  max_confidence?: number;
  created_after?: string;
  created_before?: string;
  sort_by?: SortField;
  sort_order?: SortOrder;
}

export interface DealListParams {
  page?: number;
  page_size?: number;
  pipeline_id?: string;
  owner_id?: string;
  has_threads?: boolean;
}

export interface LowConfidenceParams {
  page?: number;
  page_size?: number;
  min_confidence?: number;
  max_confidence?: number;
}

export interface AuditTrailParams {
  page?: number;
  page_size?: number;
}

// ── Bulk Action Response ─────────────────────────────────────

export interface BulkActionFailure {
  id: string;
  error: string;
}

export interface BulkActionResponse {
  succeeded: string[];
  failed: BulkActionFailure[];
}

// ── JWT User Payload ─────────────────────────────────────────

export interface JwtUser {
  sub: string;
  email: string;
  name: string;
  role: UserRole;
  exp: number;
  iat: number;
}
