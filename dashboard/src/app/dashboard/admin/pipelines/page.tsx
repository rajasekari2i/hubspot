"use client";

import { useEffect, useState, useCallback } from "react";
import type { PipelineConfig, UpdatePipelineConfigRequest } from "@/types";
import { apiClient } from "@/lib/api-client";

function IntentMappingEditor({
  rules,
  onChange,
}: {
  rules: Record<string, string>;
  onChange: (rules: Record<string, string>) => void;
}) {
  const entries = Object.entries(rules);

  function updateKey(oldKey: string, newKey: string) {
    const updated = { ...rules };
    const value = updated[oldKey];
    delete updated[oldKey];
    updated[newKey] = value;
    onChange(updated);
  }

  function updateValue(key: string, value: string) {
    onChange({ ...rules, [key]: value });
  }

  function addEntry() {
    onChange({ ...rules, "": "" });
  }

  function removeEntry(key: string) {
    const updated = { ...rules };
    delete updated[key];
    onChange(updated);
  }

  return (
    <div className="space-y-2">
      <div className="flex justify-between items-center">
        <label className="text-sm font-medium text-gray-700">
          Intent-to-Stage Mapping
        </label>
        <button
          type="button"
          onClick={addEntry}
          className="text-xs text-blue-600 hover:text-blue-800"
        >
          + Add Rule
        </button>
      </div>
      {entries.map(([key, value], idx) => (
        <div key={idx} className="flex gap-2 items-center">
          <input
            type="text"
            value={key}
            onChange={(e) => updateKey(key, e.target.value)}
            placeholder="Intent"
            className="flex-1 border rounded px-2 py-1 text-sm"
          />
          <span className="text-gray-400">&rarr;</span>
          <input
            type="text"
            value={value}
            onChange={(e) => updateValue(key, e.target.value)}
            placeholder="Stage ID"
            className="flex-1 border rounded px-2 py-1 text-sm"
          />
          <button
            type="button"
            onClick={() => removeEntry(key)}
            className="text-red-400 hover:text-red-600 text-sm"
          >
            Remove
          </button>
        </div>
      ))}
      {entries.length === 0 && (
        <p className="text-sm text-gray-400 italic">No rules configured</p>
      )}
    </div>
  );
}

function PipelineEditModal({
  pipeline,
  onClose,
  onSaved,
}: {
  pipeline: PipelineConfig;
  onClose: () => void;
  onSaved: () => void;
}) {
  const [rules, setRules] = useState(pipeline.intent_to_stage_rules);
  const [threshold, setThreshold] = useState(pipeline.recommendation_threshold);
  const [logThreshold, setLogThreshold] = useState(pipeline.logging_threshold);
  const [timeout, setTimeout] = useState(pipeline.approval_timeout_hours);
  const [maxSnoozes, setMaxSnoozes] = useState(pipeline.max_snoozes);
  const [isActive, setIsActive] = useState(pipeline.is_active);
  const [saving, setSaving] = useState(false);
  const [error, setError] = useState("");

  async function handleSubmit(e: React.FormEvent) {
    e.preventDefault();
    setSaving(true);
    setError("");

    try {
      const body: UpdatePipelineConfigRequest = {
        intent_to_stage_rules: rules,
        recommendation_threshold: threshold,
        logging_threshold: logThreshold,
        approval_timeout_hours: timeout,
        max_snoozes: maxSnoozes,
        is_active: isActive,
      };
      await apiClient.updatePipelineConfig(pipeline.id, body);
      onSaved();
    } catch (err: unknown) {
      setError(err instanceof Error ? err.message : "Failed to save pipeline config");
    } finally {
      setSaving(false);
    }
  }

  return (
    <div className="fixed inset-0 bg-black/50 flex items-center justify-center z-50 overflow-y-auto">
      <div className="bg-white rounded-lg shadow-xl w-full max-w-2xl mx-4 my-8 p-6">
        <h2 className="text-lg font-semibold mb-4">
          Configure: {pipeline.pipeline_name}
        </h2>

        {error && (
          <div className="mb-4 p-3 bg-red-50 text-red-700 text-sm rounded">{error}</div>
        )}

        <form onSubmit={handleSubmit} className="space-y-6">
          {/* Stages (read-only) */}
          <div>
            <label className="block text-sm font-medium text-gray-700 mb-2">
              Stages (synced from HubSpot)
            </label>
            <div className="flex flex-wrap gap-2">
              {pipeline.stages.map((stage) => (
                <span
                  key={stage.id}
                  className="px-2 py-1 bg-gray-100 text-sm rounded"
                >
                  {stage.order}. {stage.name}
                </span>
              ))}
            </div>
          </div>

          {/* Intent-to-Stage mapping */}
          <IntentMappingEditor rules={rules} onChange={setRules} />

          {/* Thresholds */}
          <div className="grid grid-cols-2 gap-4">
            <div>
              <label className="block text-sm font-medium text-gray-700 mb-1">
                Recommendation Threshold
              </label>
              <input
                type="range"
                min="0"
                max="1"
                step="0.05"
                value={threshold}
                onChange={(e) => setThreshold(Number(e.target.value))}
                className="w-full"
              />
              <span className="text-sm text-gray-600">
                {(threshold * 100).toFixed(0)}%
              </span>
            </div>
            <div>
              <label className="block text-sm font-medium text-gray-700 mb-1">
                Logging Threshold
              </label>
              <input
                type="range"
                min="0"
                max="1"
                step="0.05"
                value={logThreshold}
                onChange={(e) => setLogThreshold(Number(e.target.value))}
                className="w-full"
              />
              <span className="text-sm text-gray-600">
                {(logThreshold * 100).toFixed(0)}%
              </span>
            </div>
          </div>

          {/* Timeout and Snoozes */}
          <div className="grid grid-cols-2 gap-4">
            <div>
              <label className="block text-sm font-medium text-gray-700 mb-1">
                Approval Timeout (hours)
              </label>
              <input
                type="number"
                min="1"
                max="168"
                value={timeout}
                onChange={(e) => setTimeout(Number(e.target.value))}
                className="w-full border rounded px-3 py-2 text-sm"
              />
            </div>
            <div>
              <label className="block text-sm font-medium text-gray-700 mb-1">
                Max Snoozes
              </label>
              <input
                type="number"
                min="0"
                max="10"
                value={maxSnoozes}
                onChange={(e) => setMaxSnoozes(Number(e.target.value))}
                className="w-full border rounded px-3 py-2 text-sm"
              />
            </div>
          </div>

          {/* Active Toggle */}
          <div className="flex items-center gap-2">
            <input
              type="checkbox"
              id="isActive"
              checked={isActive}
              onChange={(e) => setIsActive(e.target.checked)}
              className="rounded"
            />
            <label htmlFor="isActive" className="text-sm text-gray-700">
              Pipeline is active (monitored)
            </label>
          </div>

          <div className="flex justify-end gap-3 pt-2">
            <button
              type="button"
              onClick={onClose}
              className="px-4 py-2 text-sm border rounded hover:bg-gray-50"
            >
              Cancel
            </button>
            <button
              type="submit"
              disabled={saving}
              className="px-4 py-2 text-sm bg-blue-600 text-white rounded hover:bg-blue-700 disabled:opacity-50"
            >
              {saving ? "Saving..." : "Save Changes"}
            </button>
          </div>
        </form>
      </div>
    </div>
  );
}

export default function AdminPipelinesPage() {
  const [pipelines, setPipelines] = useState<PipelineConfig[]>([]);
  const [loading, setLoading] = useState(true);
  const [editPipeline, setEditPipeline] = useState<PipelineConfig | null>(null);

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

  function handleSaved() {
    setEditPipeline(null);
    fetchPipelines();
  }

  return (
    <div>
      <h1 className="text-2xl font-semibold text-gray-900 mb-6">
        Pipeline Configuration
      </h1>

      {loading ? (
        <div className="py-12 text-center text-gray-500">Loading...</div>
      ) : (
        <div className="space-y-4">
          {pipelines.map((pipeline) => (
            <div
              key={pipeline.id}
              className="bg-white shadow rounded-lg p-5"
            >
              <div className="flex items-center justify-between mb-3">
                <div>
                  <h3 className="text-lg font-medium text-gray-900">
                    {pipeline.pipeline_name}
                  </h3>
                  <p className="text-sm text-gray-500">
                    HubSpot ID: {pipeline.hubspot_pipeline_id}
                  </p>
                </div>
                <div className="flex items-center gap-3">
                  <span
                    className={`px-2 py-0.5 text-xs rounded-full ${
                      pipeline.is_active
                        ? "bg-green-100 text-green-800"
                        : "bg-gray-100 text-gray-600"
                    }`}
                  >
                    {pipeline.is_active ? "Active" : "Inactive"}
                  </span>
                  <button
                    onClick={() => setEditPipeline(pipeline)}
                    className="px-3 py-1.5 text-sm border rounded hover:bg-gray-50"
                  >
                    Configure
                  </button>
                </div>
              </div>

              <div className="flex flex-wrap gap-2 mb-3">
                {pipeline.stages.map((stage) => (
                  <span
                    key={stage.id}
                    className="px-2 py-0.5 bg-gray-100 text-xs rounded"
                  >
                    {stage.name}
                  </span>
                ))}
              </div>

              <div className="grid grid-cols-4 gap-4 text-sm text-gray-600">
                <div>
                  Threshold:{" "}
                  <span className="font-medium">
                    {(pipeline.recommendation_threshold * 100).toFixed(0)}%
                  </span>
                </div>
                <div>
                  Log Threshold:{" "}
                  <span className="font-medium">
                    {(pipeline.logging_threshold * 100).toFixed(0)}%
                  </span>
                </div>
                <div>
                  Timeout:{" "}
                  <span className="font-medium">{pipeline.approval_timeout_hours}h</span>
                </div>
                <div>
                  Max Snoozes:{" "}
                  <span className="font-medium">{pipeline.max_snoozes}</span>
                </div>
              </div>
            </div>
          ))}

          {pipelines.length === 0 && (
            <div className="text-center text-gray-500 py-12">
              No pipelines configured. Run the pipeline sync worker to import from HubSpot.
            </div>
          )}
        </div>
      )}

      {editPipeline && (
        <PipelineEditModal
          pipeline={editPipeline}
          onClose={() => setEditPipeline(null)}
          onSaved={handleSaved}
        />
      )}
    </div>
  );
}
