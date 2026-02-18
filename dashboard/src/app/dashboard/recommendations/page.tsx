"use client";

import { useEffect, useState, useCallback } from "react";
import type {
  Recommendation,
  RecommendationStatus,
} from "@/types";
import { apiClient } from "@/lib/api-client";

const STATUS_OPTIONS: RecommendationStatus[] = [
  "pending",
  "approved",
  "rejected",
  "expired",
  "superseded",
  "conflict",
  "write_failed",
  "snoozed",
];

const CONFIDENCE_COLORS: Record<string, string> = {
  high: "bg-green-100 text-green-800",
  medium: "bg-yellow-100 text-yellow-800",
  low: "bg-red-100 text-red-800",
};

const STATUS_COLORS: Record<string, string> = {
  pending: "bg-blue-100 text-blue-800",
  approved: "bg-green-100 text-green-800",
  rejected: "bg-red-100 text-red-800",
  expired: "bg-gray-100 text-gray-600",
  superseded: "bg-purple-100 text-purple-800",
  conflict: "bg-orange-100 text-orange-800",
  write_failed: "bg-red-200 text-red-900",
  snoozed: "bg-indigo-100 text-indigo-800",
};

function confidenceLabel(score: number): string {
  if (score >= 0.85) return "high";
  if (score >= 0.7) return "medium";
  return "low";
}

export default function RecommendationsPage() {
  const [recommendations, setRecommendations] = useState<Recommendation[]>([]);
  const [total, setTotal] = useState(0);
  const [page, setPage] = useState(1);
  const [pageSize] = useState(20);
  const [statusFilter, setStatusFilter] = useState<string>("");
  const [sortBy, setSortBy] = useState("created_at");
  const [sortOrder, setSortOrder] = useState<"asc" | "desc">("desc");
  const [selected, setSelected] = useState<Set<string>>(new Set());
  const [loading, setLoading] = useState(true);

  const fetchData = useCallback(async () => {
    setLoading(true);
    try {
      const params: Record<string, string> = {
        page: String(page),
        page_size: String(pageSize),
        sort_by: sortBy,
        sort_order: sortOrder,
      };
      if (statusFilter) params.status = statusFilter;

      const data = await apiClient.getRecommendations(params);
      setRecommendations(data.items);
      setTotal(data.total);
    } catch (err) {
      console.error("Failed to load recommendations", err);
    } finally {
      setLoading(false);
    }
  }, [page, pageSize, statusFilter, sortBy, sortOrder]);

  useEffect(() => {
    fetchData();
  }, [fetchData]);

  const handleApprove = async (id: string) => {
    try {
      await apiClient.approveRecommendation(id);
      fetchData();
    } catch (err) {
      console.error("Approve failed", err);
    }
  };

  const handleReject = async (id: string, reason: string) => {
    try {
      await apiClient.rejectRecommendation(id, { reason });
      fetchData();
    } catch (err) {
      console.error("Reject failed", err);
    }
  };

  const handleBulkAction = async (action: "approve" | "reject") => {
    if (selected.size === 0) return;
    try {
      await apiClient.bulkAction({
        action,
        recommendation_ids: Array.from(selected),
        ...(action === "reject" ? { rejection_reason: "other" } : {}),
      });
      setSelected(new Set());
      fetchData();
    } catch (err) {
      console.error("Bulk action failed", err);
    }
  };

  const toggleSelect = (id: string) => {
    setSelected((prev) => {
      const next = new Set(prev);
      if (next.has(id)) next.delete(id);
      else next.add(id);
      return next;
    });
  };

  const toggleSelectAll = () => {
    if (selected.size === recommendations.length) {
      setSelected(new Set());
    } else {
      setSelected(new Set(recommendations.map((r) => r.id)));
    }
  };

  const totalPages = Math.ceil(total / pageSize);

  return (
    <div>
      <div className="flex items-center justify-between mb-6">
        <h1 className="text-2xl font-semibold text-gray-900">
          Recommendations
        </h1>
        {selected.size > 0 && (
          <div className="flex gap-2">
            <button
              onClick={() => handleBulkAction("approve")}
              className="px-3 py-1.5 text-sm bg-green-600 text-white rounded hover:bg-green-700"
            >
              Approve ({selected.size})
            </button>
            <button
              onClick={() => handleBulkAction("reject")}
              className="px-3 py-1.5 text-sm bg-red-600 text-white rounded hover:bg-red-700"
            >
              Reject ({selected.size})
            </button>
          </div>
        )}
      </div>

      {/* Filters */}
      <div className="flex gap-4 mb-4">
        <select
          value={statusFilter}
          onChange={(e) => {
            setStatusFilter(e.target.value);
            setPage(1);
          }}
          className="border rounded px-3 py-1.5 text-sm"
        >
          <option value="">All statuses</option>
          {STATUS_OPTIONS.map((s) => (
            <option key={s} value={s}>
              {s}
            </option>
          ))}
        </select>
        <select
          value={sortBy}
          onChange={(e) => setSortBy(e.target.value)}
          className="border rounded px-3 py-1.5 text-sm"
        >
          <option value="created_at">Created</option>
          <option value="confidence_score">Confidence</option>
          <option value="expires_at">Expires</option>
        </select>
        <button
          onClick={() => setSortOrder(sortOrder === "desc" ? "asc" : "desc")}
          className="border rounded px-3 py-1.5 text-sm"
        >
          {sortOrder === "desc" ? "Newest first" : "Oldest first"}
        </button>
      </div>

      {/* Table */}
      {loading ? (
        <div className="text-center py-12 text-gray-500">Loading...</div>
      ) : (
        <div className="bg-white shadow rounded-lg overflow-hidden">
          <table className="min-w-full divide-y divide-gray-200">
            <thead className="bg-gray-50">
              <tr>
                <th className="px-4 py-3 text-left">
                  <input
                    type="checkbox"
                    checked={selected.size === recommendations.length && recommendations.length > 0}
                    onChange={toggleSelectAll}
                  />
                </th>
                <th className="px-4 py-3 text-left text-xs font-medium text-gray-500 uppercase">
                  Deal
                </th>
                <th className="px-4 py-3 text-left text-xs font-medium text-gray-500 uppercase">
                  Stage Change
                </th>
                <th className="px-4 py-3 text-left text-xs font-medium text-gray-500 uppercase">
                  Confidence
                </th>
                <th className="px-4 py-3 text-left text-xs font-medium text-gray-500 uppercase">
                  Intent
                </th>
                <th className="px-4 py-3 text-left text-xs font-medium text-gray-500 uppercase">
                  Status
                </th>
                <th className="px-4 py-3 text-left text-xs font-medium text-gray-500 uppercase">
                  Created
                </th>
                <th className="px-4 py-3 text-left text-xs font-medium text-gray-500 uppercase">
                  Actions
                </th>
              </tr>
            </thead>
            <tbody className="divide-y divide-gray-200">
              {recommendations.map((rec) => {
                const label = confidenceLabel(rec.confidence_score);
                return (
                  <tr key={rec.id} className="hover:bg-gray-50">
                    <td className="px-4 py-3">
                      <input
                        type="checkbox"
                        checked={selected.has(rec.id)}
                        onChange={() => toggleSelect(rec.id)}
                      />
                    </td>
                    <td className="px-4 py-3 text-sm font-medium text-gray-900">
                      <a
                        href={`/dashboard/recommendations/${rec.id}`}
                        className="hover:text-blue-600"
                      >
                        {rec.deal_name}
                      </a>
                    </td>
                    <td className="px-4 py-3 text-sm text-gray-600">
                      {rec.current_stage_name} &rarr;{" "}
                      {rec.recommended_stage_name}
                    </td>
                    <td className="px-4 py-3">
                      <span
                        className={`inline-flex px-2 py-0.5 text-xs font-medium rounded-full ${CONFIDENCE_COLORS[label]}`}
                      >
                        {(rec.confidence_score * 100).toFixed(0)}%
                      </span>
                    </td>
                    <td className="px-4 py-3 text-sm text-gray-600">
                      {rec.intent}
                    </td>
                    <td className="px-4 py-3">
                      <span
                        className={`inline-flex px-2 py-0.5 text-xs font-medium rounded-full ${STATUS_COLORS[rec.status] || "bg-gray-100"}`}
                      >
                        {rec.status}
                      </span>
                    </td>
                    <td className="px-4 py-3 text-sm text-gray-500">
                      {new Date(rec.created_at).toLocaleDateString()}
                    </td>
                    <td className="px-4 py-3">
                      {rec.status === "pending" && (
                        <div className="flex gap-1">
                          <button
                            onClick={() => handleApprove(rec.id)}
                            className="px-2 py-1 text-xs bg-green-100 text-green-700 rounded hover:bg-green-200"
                          >
                            Approve
                          </button>
                          <button
                            onClick={() =>
                              handleReject(rec.id, "not_relevant")
                            }
                            className="px-2 py-1 text-xs bg-red-100 text-red-700 rounded hover:bg-red-200"
                          >
                            Reject
                          </button>
                        </div>
                      )}
                    </td>
                  </tr>
                );
              })}
            </tbody>
          </table>

          {/* Pagination */}
          {totalPages > 1 && (
            <div className="flex items-center justify-between px-4 py-3 bg-gray-50">
              <span className="text-sm text-gray-700">
                {total} total results
              </span>
              <div className="flex gap-2">
                <button
                  disabled={page <= 1}
                  onClick={() => setPage(page - 1)}
                  className="px-3 py-1 text-sm border rounded disabled:opacity-50"
                >
                  Previous
                </button>
                <span className="px-3 py-1 text-sm">
                  {page} / {totalPages}
                </span>
                <button
                  disabled={page >= totalPages}
                  onClick={() => setPage(page + 1)}
                  className="px-3 py-1 text-sm border rounded disabled:opacity-50"
                >
                  Next
                </button>
              </div>
            </div>
          )}
        </div>
      )}
    </div>
  );
}
