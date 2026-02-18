"use client";

import { useEffect, useState } from "react";
import { useParams, useRouter } from "next/navigation";
import type { Recommendation, DecisionTrail } from "@/types";
import { apiClient } from "@/lib/api-client";

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

function DirectionBadge({ direction }: { direction: string }) {
  const config: Record<string, { label: string; color: string }> = {
    forward: { label: "Forward", color: "bg-green-100 text-green-700" },
    backward: { label: "Backward", color: "bg-red-100 text-red-700" },
    neutral: { label: "Neutral", color: "bg-gray-100 text-gray-700" },
  };
  const c = config[direction] || config.neutral;
  return (
    <span className={`inline-flex px-2 py-0.5 text-xs font-medium rounded-full ${c.color}`}>
      {c.label}
    </span>
  );
}

export default function DecisionTrailPage() {
  const params = useParams();
  const router = useRouter();
  const id = params.id as string;

  const [trail, setTrail] = useState<DecisionTrail | null>(null);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    async function load() {
      try {
        const data = await apiClient.getDecisionTrail(id);
        setTrail(data);
      } catch (err) {
        console.error("Failed to load decision trail", err);
      } finally {
        setLoading(false);
      }
    }
    load();
  }, [id]);

  if (loading) {
    return <div className="py-12 text-center text-gray-500">Loading...</div>;
  }

  if (!trail) {
    return <div className="py-12 text-center text-gray-500">Not found</div>;
  }

  return (
    <div>
      <button
        onClick={() => router.back()}
        className="mb-4 text-sm text-blue-600 hover:text-blue-800"
      >
        &larr; Back to recommendations
      </button>

      <h1 className="text-2xl font-semibold text-gray-900 mb-6">
        Decision Trail
      </h1>

      {/* Pipeline visualization */}
      <div className="space-y-6">
        {/* Step 1: Triggering Email */}
        <div className="bg-white shadow rounded-lg p-6">
          <div className="flex items-center gap-2 mb-3">
            <div className="w-8 h-8 bg-blue-500 text-white rounded-full flex items-center justify-center text-sm font-medium">
              1
            </div>
            <h2 className="text-lg font-medium text-gray-900">
              Triggering Email
            </h2>
          </div>
          {trail.email ? (
            <div className="ml-10 space-y-2">
              <p className="text-sm">
                <span className="font-medium text-gray-700">Subject:</span>{" "}
                {trail.email.subject}
              </p>
              <p className="text-sm">
                <span className="font-medium text-gray-700">From:</span>{" "}
                {trail.email.from_address}
              </p>
              <p className="text-sm">
                <span className="font-medium text-gray-700">Received:</span>{" "}
                {new Date(trail.email.received_at).toLocaleString()}
              </p>
              <div className="mt-2 p-3 bg-gray-50 rounded text-sm text-gray-600 italic">
                {trail.email.excerpt}
              </div>
            </div>
          ) : (
            <p className="ml-10 text-sm text-gray-500">Email data unavailable</p>
          )}
        </div>

        {/* Connector */}
        <div className="ml-4 h-6 border-l-2 border-gray-300" />

        {/* Step 2: AI Classification */}
        <div className="bg-white shadow rounded-lg p-6">
          <div className="flex items-center gap-2 mb-3">
            <div className="w-8 h-8 bg-purple-500 text-white rounded-full flex items-center justify-center text-sm font-medium">
              2
            </div>
            <h2 className="text-lg font-medium text-gray-900">
              AI Classification
            </h2>
          </div>
          {trail.classification ? (
            <div className="ml-10 grid grid-cols-2 gap-4">
              <div>
                <p className="text-xs text-gray-500 uppercase">Intent</p>
                <p className="text-sm font-medium">{trail.classification.intent}</p>
              </div>
              <div>
                <p className="text-xs text-gray-500 uppercase">Confidence</p>
                <p className="text-sm font-medium">
                  {(trail.classification.confidence_score * 100).toFixed(1)}%
                </p>
              </div>
              <div>
                <p className="text-xs text-gray-500 uppercase">Direction</p>
                <DirectionBadge direction={trail.classification.direction} />
              </div>
              <div>
                <p className="text-xs text-gray-500 uppercase">Model</p>
                <p className="text-sm">{trail.classification.llm_model}</p>
              </div>
              <div className="col-span-2">
                <p className="text-xs text-gray-500 uppercase">Reasoning</p>
                <p className="text-sm text-gray-700 mt-1">
                  {trail.classification.reasoning}
                </p>
              </div>
              {trail.classification.key_phrases.length > 0 && (
                <div className="col-span-2">
                  <p className="text-xs text-gray-500 uppercase mb-1">
                    Key Phrases
                  </p>
                  <div className="flex flex-wrap gap-1">
                    {trail.classification.key_phrases.map((phrase, i) => (
                      <span
                        key={i}
                        className="px-2 py-0.5 bg-gray-100 text-gray-700 text-xs rounded"
                      >
                        {phrase}
                      </span>
                    ))}
                  </div>
                </div>
              )}
            </div>
          ) : (
            <p className="ml-10 text-sm text-gray-500">Classification data unavailable</p>
          )}
        </div>

        {/* Connector */}
        <div className="ml-4 h-6 border-l-2 border-gray-300" />

        {/* Step 3: Stage Mapping */}
        <div className="bg-white shadow rounded-lg p-6">
          <div className="flex items-center gap-2 mb-3">
            <div className="w-8 h-8 bg-yellow-500 text-white rounded-full flex items-center justify-center text-sm font-medium">
              3
            </div>
            <h2 className="text-lg font-medium text-gray-900">
              Stage Mapping
            </h2>
          </div>
          {trail.mapping ? (
            <div className="ml-10 space-y-2">
              <p className="text-sm">
                <span className="font-medium text-gray-700">Pipeline:</span>{" "}
                {trail.mapping.pipeline_name}
              </p>
              <div className="flex items-center gap-2 text-sm">
                <span className="px-2 py-1 bg-gray-100 rounded">
                  {trail.mapping.current_stage}
                </span>
                <span className="text-gray-400">&rarr;</span>
                <span className="px-2 py-1 bg-blue-100 text-blue-800 rounded">
                  {trail.mapping.recommended_stage}
                </span>
              </div>
              {trail.mapping.rule_applied && (
                <p className="text-xs text-gray-500">
                  Rule: {trail.mapping.rule_applied}
                </p>
              )}
            </div>
          ) : (
            <p className="ml-10 text-sm text-gray-500">Mapping data unavailable</p>
          )}
        </div>

        {/* Connector */}
        <div className="ml-4 h-6 border-l-2 border-gray-300" />

        {/* Step 4: User Action */}
        <div className="bg-white shadow rounded-lg p-6">
          <div className="flex items-center gap-2 mb-3">
            <div className="w-8 h-8 bg-green-500 text-white rounded-full flex items-center justify-center text-sm font-medium">
              4
            </div>
            <h2 className="text-lg font-medium text-gray-900">User Action</h2>
          </div>
          {trail.user_action ? (
            <div className="ml-10 space-y-2">
              <div className="flex items-center gap-2">
                <span
                  className={`px-2 py-0.5 text-xs font-medium rounded-full ${STATUS_COLORS[trail.user_action.action] || "bg-gray-100"}`}
                >
                  {trail.user_action.action}
                </span>
                {trail.user_action.actor && (
                  <span className="text-sm text-gray-600">
                    by {trail.user_action.actor}
                  </span>
                )}
              </div>
              {trail.user_action.acted_at && (
                <p className="text-xs text-gray-500">
                  {new Date(trail.user_action.acted_at).toLocaleString()}
                </p>
              )}
              {trail.user_action.rejection_reason && (
                <p className="text-sm text-gray-600">
                  Reason: {trail.user_action.rejection_reason}
                </p>
              )}
            </div>
          ) : (
            <p className="ml-10 text-sm text-gray-500 italic">
              Awaiting user action
            </p>
          )}
        </div>

        {/* Step 5: CRM Result */}
        {trail.crm_result && (
          <>
            <div className="ml-4 h-6 border-l-2 border-gray-300" />
            <div className="bg-white shadow rounded-lg p-6">
              <div className="flex items-center gap-2 mb-3">
                <div className="w-8 h-8 bg-teal-500 text-white rounded-full flex items-center justify-center text-sm font-medium">
                  5
                </div>
                <h2 className="text-lg font-medium text-gray-900">
                  CRM Result
                </h2>
              </div>
              <div className="ml-10 space-y-2">
                <p className="text-sm">
                  <span className="font-medium text-gray-700">Status:</span>{" "}
                  <span
                    className={
                      trail.crm_result.status === "success"
                        ? "text-green-600"
                        : "text-red-600"
                    }
                  >
                    {trail.crm_result.status}
                  </span>
                </p>
                {trail.crm_result.updated_at && (
                  <p className="text-xs text-gray-500">
                    Updated: {new Date(trail.crm_result.updated_at).toLocaleString()}
                  </p>
                )}
                {trail.crm_result.error && (
                  <p className="text-sm text-red-600">
                    Error: {trail.crm_result.error}
                  </p>
                )}
              </div>
            </div>
          </>
        )}
      </div>
    </div>
  );
}
