"use client";

import { useEffect, useState, useCallback } from "react";
import type { PipelineConfig, UpdatePipelineConfigRequest } from "@/types";
import { apiClient } from "@/lib/api-client";

export default function AdminThresholdsPage() {
  const [pipelines, setPipelines] = useState<PipelineConfig[]>([]);
  const [loading, setLoading] = useState(true);
  const [saving, setSaving] = useState<string | null>(null);
  const [edits, setEdits] = useState<
    Record<string, Partial<UpdatePipelineConfigRequest>>
  >({});

  const fetchPipelines = useCallback(async () => {
    setLoading(true);
    try {
      const data = await apiClient.getPipelineConfigs();
      setPipelines(data.items);
    } catch (err) {
      console.error("Failed to load pipelines", err);
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    fetchPipelines();
  }, [fetchPipelines]);

  function getEdit(id: string): Partial<UpdatePipelineConfigRequest> {
    return edits[id] ?? {};
  }

  function updateEdit(id: string, field: string, value: number) {
    setEdits((prev) => ({
      ...prev,
      [id]: { ...prev[id], [field]: value },
    }));
  }

  function hasChanges(pipeline: PipelineConfig): boolean {
    const edit = getEdit(pipeline.id);
    return Object.keys(edit).length > 0;
  }

  async function handleSave(pipeline: PipelineConfig) {
    const edit = getEdit(pipeline.id);
    if (!Object.keys(edit).length) return;

    setSaving(pipeline.id);
    try {
      await apiClient.updatePipelineConfig(pipeline.id, edit);
      setEdits((prev) => {
        const next = { ...prev };
        delete next[pipeline.id];
        return next;
      });
      fetchPipelines();
    } catch (err) {
      console.error("Failed to save thresholds", err);
    } finally {
      setSaving(null);
    }
  }

  function getDisplayValue(
    pipeline: PipelineConfig,
    field: keyof PipelineConfig,
  ): number {
    const edit = getEdit(pipeline.id);
    if (field in edit) {
      return edit[field as keyof UpdatePipelineConfigRequest] as number;
    }
    return pipeline[field] as number;
  }

  return (
    <div>
      <h1 className="text-2xl font-semibold text-gray-900 mb-6">
        Threshold Configuration
      </h1>

      {loading ? (
        <div className="py-12 text-center text-gray-500">Loading...</div>
      ) : (
        <div className="space-y-6">
          {pipelines.map((pipeline) => (
            <div key={pipeline.id} className="bg-white shadow rounded-lg p-6">
              <div className="flex items-center justify-between mb-4">
                <h3 className="text-lg font-medium text-gray-900">
                  {pipeline.pipeline_name}
                </h3>
                {hasChanges(pipeline) && (
                  <button
                    onClick={() => handleSave(pipeline)}
                    disabled={saving === pipeline.id}
                    className="px-4 py-1.5 text-sm bg-blue-600 text-white rounded hover:bg-blue-700 disabled:opacity-50"
                  >
                    {saving === pipeline.id ? "Saving..." : "Save Changes"}
                  </button>
                )}
              </div>

              <div className="space-y-6">
                {/* Recommendation Threshold */}
                <div>
                  <div className="flex justify-between text-sm mb-1">
                    <label className="font-medium text-gray-700">
                      Recommendation Threshold
                    </label>
                    <span className="text-gray-600">
                      {(
                        getDisplayValue(pipeline, "recommendation_threshold") * 100
                      ).toFixed(0)}
                      %
                    </span>
                  </div>
                  <input
                    type="range"
                    min="0"
                    max="1"
                    step="0.05"
                    value={getDisplayValue(pipeline, "recommendation_threshold")}
                    onChange={(e) =>
                      updateEdit(
                        pipeline.id,
                        "recommendation_threshold",
                        Number(e.target.value),
                      )
                    }
                    className="w-full"
                  />
                  <p className="text-xs text-gray-500 mt-1">
                    Minimum confidence score required to generate a recommendation
                  </p>
                </div>

                {/* Logging Threshold */}
                <div>
                  <div className="flex justify-between text-sm mb-1">
                    <label className="font-medium text-gray-700">
                      Logging Threshold
                    </label>
                    <span className="text-gray-600">
                      {(
                        getDisplayValue(pipeline, "logging_threshold") * 100
                      ).toFixed(0)}
                      %
                    </span>
                  </div>
                  <input
                    type="range"
                    min="0"
                    max="1"
                    step="0.05"
                    value={getDisplayValue(pipeline, "logging_threshold")}
                    onChange={(e) =>
                      updateEdit(
                        pipeline.id,
                        "logging_threshold",
                        Number(e.target.value),
                      )
                    }
                    className="w-full"
                  />
                  <p className="text-xs text-gray-500 mt-1">
                    Minimum confidence for RevOps logging (below recommendation threshold)
                  </p>
                </div>

                {/* Approval Timeout */}
                <div>
                  <div className="flex justify-between text-sm mb-1">
                    <label className="font-medium text-gray-700">
                      Approval Timeout
                    </label>
                    <span className="text-gray-600">
                      {getDisplayValue(pipeline, "approval_timeout_hours")} hours
                    </span>
                  </div>
                  <input
                    type="range"
                    min="1"
                    max="168"
                    step="1"
                    value={getDisplayValue(pipeline, "approval_timeout_hours")}
                    onChange={(e) =>
                      updateEdit(
                        pipeline.id,
                        "approval_timeout_hours",
                        Number(e.target.value),
                      )
                    }
                    className="w-full"
                  />
                  <p className="text-xs text-gray-500 mt-1">
                    Hours before a pending recommendation expires automatically
                  </p>
                </div>

                {/* Max Snoozes */}
                <div>
                  <div className="flex justify-between text-sm mb-1">
                    <label className="font-medium text-gray-700">
                      Max Snoozes
                    </label>
                    <span className="text-gray-600">
                      {getDisplayValue(pipeline, "max_snoozes")}
                    </span>
                  </div>
                  <input
                    type="range"
                    min="0"
                    max="10"
                    step="1"
                    value={getDisplayValue(pipeline, "max_snoozes")}
                    onChange={(e) =>
                      updateEdit(
                        pipeline.id,
                        "max_snoozes",
                        Number(e.target.value),
                      )
                    }
                    className="w-full"
                  />
                  <p className="text-xs text-gray-500 mt-1">
                    Maximum number of times a recommendation can be snoozed
                  </p>
                </div>
              </div>
            </div>
          ))}

          {pipelines.length === 0 && (
            <div className="text-center text-gray-500 py-12">
              No pipelines configured.
            </div>
          )}
        </div>
      )}
    </div>
  );
}
