"use client";

import { useEffect, useState } from "react";
import type { AnalyticsOverview } from "@/types";
import { apiClient } from "@/lib/api-client";

const PERIOD_OPTIONS = [
  { value: 7, label: "Last 7 days" },
  { value: 14, label: "Last 14 days" },
  { value: 30, label: "Last 30 days" },
  { value: 90, label: "Last 90 days" },
];

function MetricCard({
  label,
  value,
  subtext,
  color = "text-gray-900",
}: {
  label: string;
  value: string | number;
  subtext?: string;
  color?: string;
}) {
  return (
    <div className="bg-white shadow rounded-lg p-5">
      <p className="text-sm font-medium text-gray-500 uppercase tracking-wide">
        {label}
      </p>
      <p className={`mt-2 text-3xl font-semibold ${color}`}>{value}</p>
      {subtext && <p className="mt-1 text-sm text-gray-500">{subtext}</p>}
    </div>
  );
}

function BarChart({
  data,
  title,
}: {
  data: Record<string, number>;
  title: string;
}) {
  const entries = Object.entries(data);
  const max = Math.max(...entries.map(([, v]) => v), 1);

  return (
    <div className="bg-white shadow rounded-lg p-5">
      <h3 className="text-sm font-medium text-gray-700 mb-4">{title}</h3>
      <div className="space-y-3">
        {entries.map(([key, value]) => (
          <div key={key}>
            <div className="flex justify-between text-sm mb-1">
              <span className="text-gray-600">{key}</span>
              <span className="font-medium">{value}</span>
            </div>
            <div className="w-full bg-gray-200 rounded-full h-2">
              <div
                className="bg-blue-500 h-2 rounded-full"
                style={{ width: `${(value / max) * 100}%` }}
              />
            </div>
          </div>
        ))}
      </div>
    </div>
  );
}

export default function AnalyticsPage() {
  const [data, setData] = useState<AnalyticsOverview | null>(null);
  const [period, setPeriod] = useState(7);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    async function load() {
      setLoading(true);
      try {
        const result = await apiClient.getAnalyticsOverview(period);
        setData(result);
      } catch (err) {
        console.error("Failed to load analytics", err);
      } finally {
        setLoading(false);
      }
    }
    load();
  }, [period]);

  if (loading || !data) {
    return <div className="py-12 text-center text-gray-500">Loading analytics...</div>;
  }

  const recs = data.recommendations;

  return (
    <div>
      <div className="flex items-center justify-between mb-6">
        <h1 className="text-2xl font-semibold text-gray-900">Analytics</h1>
        <select
          value={period}
          onChange={(e) => setPeriod(Number(e.target.value))}
          className="border rounded px-3 py-1.5 text-sm"
        >
          {PERIOD_OPTIONS.map((opt) => (
            <option key={opt.value} value={opt.value}>
              {opt.label}
            </option>
          ))}
        </select>
      </div>

      {/* KPI Cards */}
      <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-4 mb-8">
        <MetricCard
          label="Total Recommendations"
          value={recs.total}
        />
        <MetricCard
          label="Approval Rate"
          value={`${(recs.approval_rate * 100).toFixed(1)}%`}
          color={recs.approval_rate >= 0.7 ? "text-green-600" : "text-yellow-600"}
        />
        <MetricCard
          label="Approved"
          value={recs.approved}
          color="text-green-600"
          subtext={`${recs.rejected} rejected, ${recs.expired} expired`}
        />
        <MetricCard
          label="Pending"
          value={recs.pending}
          color="text-blue-600"
        />
      </div>

      {/* Charts Row */}
      <div className="grid grid-cols-1 lg:grid-cols-2 gap-6 mb-8">
        <BarChart
          title="Rejections by Reason"
          data={data.rejections_by_reason}
        />

        {/* Confidence Distribution */}
        <div className="bg-white shadow rounded-lg p-5">
          <h3 className="text-sm font-medium text-gray-700 mb-4">
            Confidence Distribution
          </h3>
          <div className="grid grid-cols-3 gap-4">
            <div className="text-center">
              <p className="text-2xl font-semibold text-gray-900">
                {(data.confidence.average * 100).toFixed(1)}%
              </p>
              <p className="text-xs text-gray-500 uppercase mt-1">Average</p>
            </div>
            <div className="text-center">
              <p className="text-2xl font-semibold text-gray-900">
                {(data.confidence.p50 * 100).toFixed(1)}%
              </p>
              <p className="text-xs text-gray-500 uppercase mt-1">Median (p50)</p>
            </div>
            <div className="text-center">
              <p className="text-2xl font-semibold text-gray-900">
                {(data.confidence.p95 * 100).toFixed(1)}%
              </p>
              <p className="text-xs text-gray-500 uppercase mt-1">p95</p>
            </div>
          </div>
        </div>
      </div>

      {/* Latency and Coverage */}
      <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
        {/* Latency Gauges */}
        <div className="bg-white shadow rounded-lg p-5">
          <h3 className="text-sm font-medium text-gray-700 mb-4">
            Processing Latency
          </h3>
          <div className="grid grid-cols-2 gap-4">
            <div>
              <p className="text-xs text-gray-500 uppercase">Email &rarr; Notification (p50)</p>
              <p className="text-xl font-semibold mt-1">
                {data.latency.email_to_notification_p50_seconds.toFixed(1)}s
              </p>
            </div>
            <div>
              <p className="text-xs text-gray-500 uppercase">Email &rarr; Notification (p95)</p>
              <p className="text-xl font-semibold mt-1">
                {data.latency.email_to_notification_p95_seconds.toFixed(1)}s
              </p>
            </div>
            <div>
              <p className="text-xs text-gray-500 uppercase">Approval &rarr; CRM (p50)</p>
              <p className="text-xl font-semibold mt-1">
                {data.latency.approval_to_crm_p50_seconds.toFixed(1)}s
              </p>
            </div>
            <div>
              <p className="text-xs text-gray-500 uppercase">Approval &rarr; CRM (p95)</p>
              <p className="text-xl font-semibold mt-1">
                {data.latency.approval_to_crm_p95_seconds.toFixed(1)}s
              </p>
            </div>
          </div>
        </div>

        {/* Deal Coverage */}
        <div className="bg-white shadow rounded-lg p-5">
          <h3 className="text-sm font-medium text-gray-700 mb-4">
            Deal Coverage
          </h3>
          <div className="flex items-center gap-8">
            <div className="relative w-28 h-28">
              <svg className="w-28 h-28 -rotate-90" viewBox="0 0 100 100">
                <circle
                  cx="50"
                  cy="50"
                  r="42"
                  fill="none"
                  stroke="#e5e7eb"
                  strokeWidth="12"
                />
                <circle
                  cx="50"
                  cy="50"
                  r="42"
                  fill="none"
                  stroke="#3b82f6"
                  strokeWidth="12"
                  strokeLinecap="round"
                  strokeDasharray={`${data.deal_coverage.coverage_percent * 2.64} ${264 - data.deal_coverage.coverage_percent * 2.64}`}
                />
              </svg>
              <div className="absolute inset-0 flex items-center justify-center">
                <span className="text-lg font-semibold">
                  {data.deal_coverage.coverage_percent.toFixed(0)}%
                </span>
              </div>
            </div>
            <div className="space-y-2">
              <p className="text-sm">
                <span className="font-medium">{data.deal_coverage.deals_with_threads}</span>{" "}
                <span className="text-gray-500">deals with email threads</span>
              </p>
              <p className="text-sm">
                <span className="font-medium">{data.deal_coverage.total_active_deals}</span>{" "}
                <span className="text-gray-500">total active deals</span>
              </p>
            </div>
          </div>
        </div>
      </div>
    </div>
  );
}
