"use client";

import { useEffect, useState, useCallback } from "react";
import type { HealthStatus, HealthCheck, HealthCheckStatus } from "@/types";
import { apiClient } from "@/lib/api-client";

const STATUS_STYLES: Record<HealthCheckStatus, { bg: string; text: string; label: string }> = {
  ok: { bg: "bg-green-100", text: "text-green-800", label: "Operational" },
  degraded: { bg: "bg-yellow-100", text: "text-yellow-800", label: "Degraded" },
  down: { bg: "bg-red-100", text: "text-red-800", label: "Down" },
};

const SERVICE_LABELS: Record<string, { name: string; description: string }> = {
  database: { name: "PostgreSQL", description: "Primary data store" },
  redis: { name: "Redis", description: "Cache, rate limiting, DLQ" },
  gmail_api: { name: "Gmail API", description: "Email monitoring" },
  hubspot_api: { name: "HubSpot API", description: "CRM integration" },
  llm_api: { name: "LLM Provider", description: "Intent classification" },
  slack_api: { name: "Slack API", description: "Notifications & actions" },
};

function StatusIndicator({ status }: { status: HealthCheckStatus }) {
  const style = STATUS_STYLES[status] ?? STATUS_STYLES.down;
  return (
    <span className={`px-2.5 py-0.5 text-xs font-medium rounded-full ${style.bg} ${style.text}`}>
      {style.label}
    </span>
  );
}

function ServiceCard({
  serviceKey,
  check,
}: {
  serviceKey: string;
  check: HealthCheck;
}) {
  const svc = SERVICE_LABELS[serviceKey] ?? { name: serviceKey, description: "" };

  return (
    <div className="bg-white shadow rounded-lg p-5">
      <div className="flex items-center justify-between mb-2">
        <h3 className="text-sm font-semibold text-gray-900">{svc.name}</h3>
        <StatusIndicator status={check.status} />
      </div>
      <p className="text-xs text-gray-500 mb-3">{svc.description}</p>

      <div className="space-y-1 text-xs text-gray-600">
        {check.latency_ms !== null && (
          <div className="flex justify-between">
            <span>Latency</span>
            <span className="font-medium">{check.latency_ms}ms</span>
          </div>
        )}
        <div className="flex justify-between">
          <span>Last checked</span>
          <span className="font-medium">
            {new Date(check.last_checked).toLocaleTimeString()}
          </span>
        </div>
        {check.error && (
          <div className="mt-2 p-2 bg-red-50 rounded text-red-700 text-xs">
            {check.error}
          </div>
        )}
      </div>
    </div>
  );
}

export default function AdminHealthPage() {
  const [health, setHealth] = useState<HealthStatus | null>(null);
  const [loading, setLoading] = useState(true);
  const [autoRefresh, setAutoRefresh] = useState(true);

  const fetchHealth = useCallback(async () => {
    try {
      const data = await apiClient.getHealth();
      setHealth(data);
    } catch (err) {
      console.error("Failed to load health status", err);
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    fetchHealth();
  }, [fetchHealth]);

  useEffect(() => {
    if (!autoRefresh) return;
    const interval = setInterval(fetchHealth, 30_000);
    return () => clearInterval(interval);
  }, [autoRefresh, fetchHealth]);

  const overallStatusStyle = health
    ? {
        healthy: { bg: "bg-green-50", border: "border-green-500", text: "text-green-800" },
        degraded: { bg: "bg-yellow-50", border: "border-yellow-500", text: "text-yellow-800" },
        unhealthy: { bg: "bg-red-50", border: "border-red-500", text: "text-red-800" },
      }[health.status]
    : null;

  return (
    <div>
      <div className="flex items-center justify-between mb-6">
        <h1 className="text-2xl font-semibold text-gray-900">System Health</h1>
        <div className="flex items-center gap-4">
          <label className="flex items-center gap-2 text-sm text-gray-600">
            <input
              type="checkbox"
              checked={autoRefresh}
              onChange={(e) => setAutoRefresh(e.target.checked)}
              className="rounded"
            />
            Auto-refresh (30s)
          </label>
          <button
            onClick={fetchHealth}
            className="px-3 py-1.5 text-sm border rounded hover:bg-gray-50"
          >
            Refresh Now
          </button>
        </div>
      </div>

      {loading ? (
        <div className="py-12 text-center text-gray-500">Loading health status...</div>
      ) : health ? (
        <>
          {/* Overall Status Banner */}
          {overallStatusStyle && (
            <div
              className={`mb-6 p-4 rounded-lg border-l-4 ${overallStatusStyle.bg} ${overallStatusStyle.border}`}
            >
              <div className="flex items-center justify-between">
                <div>
                  <h2 className={`text-lg font-semibold ${overallStatusStyle.text}`}>
                    System is {health.status}
                  </h2>
                  <p className="text-sm text-gray-600">
                    Last updated: {new Date(health.timestamp).toLocaleString()}
                  </p>
                </div>
              </div>
            </div>
          )}

          {/* Service Cards Grid */}
          <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 gap-4">
            {Object.entries(health.checks).map(([key, check]) => (
              <ServiceCard key={key} serviceKey={key} check={check} />
            ))}
          </div>
        </>
      ) : (
        <div className="py-12 text-center text-red-500">
          Failed to load health status. Backend may be unreachable.
        </div>
      )}
    </div>
  );
}
