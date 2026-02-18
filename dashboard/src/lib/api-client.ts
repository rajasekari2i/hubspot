// ──────────────────────────────────────────────────────────────
// Typed API client with auth token handling, error mapping,
// and pagination support.
// ──────────────────────────────────────────────────────────────

import type {
  AnalyticsOverview,
  AuditLogEntry,
  AuditTrailParams,
  ApproveRequest,
  BulkActionRequest,
  BulkActionResponse,
  CreatePromptVersionRequest,
  CreateUserRequest,
  Deal,
  DealListParams,
  DecisionTrail,
  HealthStatus,
  LowConfidenceClassification,
  LowConfidenceParams,
  PaginatedResponse,
  PipelineConfig,
  PromptVersion,
  Recommendation,
  RecommendationList,
  RecommendationListParams,
  RejectRequest,
  SnoozeRequest,
  UpdatePipelineConfigRequest,
  UpdateUserRequest,
  UserConfig,
} from '@/types';

// ── Configuration ────────────────────────────────────────────

const API_BASE = process.env.NEXT_PUBLIC_API_URL || 'http://localhost:8000/api/v1';
const AUTH_TOKEN_KEY = 'auth_token';

// ── Error Class ──────────────────────────────────────────────

export class ApiError extends Error {
  public readonly status: number;
  public readonly detail: string;
  public readonly traceId: string | null;

  constructor(status: number, message: string, detail?: string, traceId?: string) {
    super(message);
    this.name = 'ApiError';
    this.status = status;
    this.detail = detail ?? message;
    this.traceId = traceId ?? null;
  }
}

// ── Token Helpers ────────────────────────────────────────────

function getToken(): string | null {
  if (typeof window === 'undefined') return null;
  return localStorage.getItem(AUTH_TOKEN_KEY);
}

// ── Generic Fetch ────────────────────────────────────────────

interface FetchOptions extends Omit<RequestInit, 'body'> {
  body?: unknown;
  params?: Record<string, string | number | boolean | undefined>;
}

async function apiFetch<T>(path: string, options: FetchOptions = {}): Promise<T> {
  const { body, params, headers: extraHeaders, ...rest } = options;

  // Build URL with query parameters
  let url = `${API_BASE}${path}`;
  if (params) {
    const searchParams = new URLSearchParams();
    for (const [key, value] of Object.entries(params)) {
      if (value !== undefined && value !== null) {
        searchParams.set(key, String(value));
      }
    }
    const qs = searchParams.toString();
    if (qs) {
      url = `${url}?${qs}`;
    }
  }

  // Build headers
  const headers: Record<string, string> = {
    'Content-Type': 'application/json',
    ...(extraHeaders as Record<string, string>),
  };

  const token = getToken();
  if (token) {
    headers['Authorization'] = `Bearer ${token}`;
  }

  // Execute request
  const response = await fetch(url, {
    ...rest,
    headers,
    body: body !== undefined ? JSON.stringify(body) : undefined,
  });

  // Handle auth failures
  if (response.status === 401) {
    if (typeof window !== 'undefined') {
      localStorage.removeItem(AUTH_TOKEN_KEY);
      window.location.href = '/login';
    }
    throw new ApiError(401, 'Authentication required');
  }

  // Handle errors
  if (!response.ok) {
    let errorMessage = `Request failed with status ${response.status}`;
    let detail = '';
    let traceId: string | undefined;

    try {
      const errorBody = await response.json();
      errorMessage = errorBody.error || errorMessage;
      detail = errorBody.detail || '';
      traceId = errorBody.trace_id;
    } catch {
      // Response body was not JSON
    }

    throw new ApiError(response.status, errorMessage, detail, traceId);
  }

  // 204 No Content
  if (response.status === 204) {
    return undefined as T;
  }

  return response.json() as Promise<T>;
}

// ── Recommendations ──────────────────────────────────────────

export async function getRecommendations(
  params?: RecommendationListParams,
): Promise<RecommendationList> {
  return apiFetch<RecommendationList>('/recommendations', {
    params: params as Record<string, string | number | boolean | undefined>,
  });
}

export async function getRecommendation(id: string): Promise<Recommendation> {
  return apiFetch<Recommendation>(`/recommendations/${id}`);
}

export async function approveRecommendation(
  id: string,
  body: ApproveRequest = {},
): Promise<Recommendation> {
  return apiFetch<Recommendation>(`/recommendations/${id}/approve`, {
    method: 'POST',
    body,
  });
}

export async function rejectRecommendation(
  id: string,
  body: RejectRequest,
): Promise<Recommendation> {
  return apiFetch<Recommendation>(`/recommendations/${id}/reject`, {
    method: 'POST',
    body,
  });
}

export async function snoozeRecommendation(
  id: string,
  body: SnoozeRequest = {},
): Promise<Recommendation> {
  return apiFetch<Recommendation>(`/recommendations/${id}/snooze`, {
    method: 'POST',
    body,
  });
}

export async function bulkAction(body: BulkActionRequest): Promise<BulkActionResponse> {
  return apiFetch<BulkActionResponse>('/recommendations/bulk', {
    method: 'POST',
    body,
  });
}

export async function getDecisionTrail(id: string): Promise<DecisionTrail> {
  return apiFetch<DecisionTrail>(`/recommendations/${id}/trail`);
}

// ── Deals ────────────────────────────────────────────────────

export async function getDeals(
  params?: DealListParams,
): Promise<PaginatedResponse<Deal>> {
  return apiFetch<PaginatedResponse<Deal>>('/deals', {
    params: params as Record<string, string | number | boolean | undefined>,
  });
}

export async function getDeal(id: string): Promise<Deal> {
  return apiFetch<Deal>(`/deals/${id}`);
}

// ── Analytics ────────────────────────────────────────────────

export async function getAnalyticsOverview(
  periodDays: number = 7,
): Promise<AnalyticsOverview> {
  return apiFetch<AnalyticsOverview>('/analytics/overview', {
    params: { period_days: periodDays },
  });
}

export async function getLowConfidenceClassifications(
  params?: LowConfidenceParams,
): Promise<PaginatedResponse<LowConfidenceClassification>> {
  return apiFetch<PaginatedResponse<LowConfidenceClassification>>(
    '/analytics/classifications/low-confidence',
    {
      params: params as Record<string, string | number | boolean | undefined>,
    },
  );
}

// ── Audit ────────────────────────────────────────────────────

export async function getAuditTrail(
  entityType: string,
  entityId: string,
  params?: AuditTrailParams,
): Promise<PaginatedResponse<AuditLogEntry>> {
  return apiFetch<PaginatedResponse<AuditLogEntry>>(
    `/audit/trail/${entityType}/${entityId}`,
    {
      params: params as Record<string, string | number | boolean | undefined>,
    },
  );
}

// ── Admin: Users ─────────────────────────────────────────────

export async function getUsers(): Promise<PaginatedResponse<UserConfig>> {
  return apiFetch<PaginatedResponse<UserConfig>>('/admin/users');
}

export async function createUser(body: CreateUserRequest): Promise<UserConfig> {
  return apiFetch<UserConfig>('/admin/users', {
    method: 'POST',
    body,
  });
}

export async function updateUser(
  id: string,
  body: UpdateUserRequest,
): Promise<UserConfig> {
  return apiFetch<UserConfig>(`/admin/users/${id}`, {
    method: 'PATCH',
    body,
  });
}

// ── Admin: Pipelines ─────────────────────────────────────────

export async function getPipelineConfigs(): Promise<PaginatedResponse<PipelineConfig>> {
  return apiFetch<PaginatedResponse<PipelineConfig>>('/admin/pipelines');
}

export async function updatePipelineConfig(
  id: string,
  body: UpdatePipelineConfigRequest,
): Promise<PipelineConfig> {
  return apiFetch<PipelineConfig>(`/admin/pipelines/${id}`, {
    method: 'PATCH',
    body,
  });
}

// ── Admin: Prompts ───────────────────────────────────────────

export async function getPromptVersions(): Promise<PaginatedResponse<PromptVersion>> {
  return apiFetch<PaginatedResponse<PromptVersion>>('/admin/prompts');
}

export async function createPromptVersion(
  body: CreatePromptVersionRequest,
): Promise<PromptVersion> {
  return apiFetch<PromptVersion>('/admin/prompts', {
    method: 'POST',
    body,
  });
}

export async function activatePromptVersion(id: string): Promise<PromptVersion> {
  return apiFetch<PromptVersion>(`/admin/prompts/${id}/activate`, {
    method: 'POST',
  });
}

// ── Health ───────────────────────────────────────────────────

export async function getHealth(): Promise<HealthStatus> {
  return apiFetch<HealthStatus>('/health');
}

// ── Namespace Export ─────────────────────────────────────────
// Provides a single object for consumers that prefer
// `apiClient.getRecommendations(...)` style usage.

export const apiClient = {
  getRecommendations,
  getRecommendation,
  approveRecommendation,
  rejectRecommendation,
  snoozeRecommendation,
  bulkAction,
  getDecisionTrail,
  getDeals,
  getDeal,
  getAnalyticsOverview,
  getLowConfidenceClassifications,
  getAuditTrail,
  getUsers,
  createUser,
  updateUser,
  getPipelineConfigs,
  updatePipelineConfig,
  getPromptVersions,
  createPromptVersion,
  activatePromptVersion,
  getHealth,
};
