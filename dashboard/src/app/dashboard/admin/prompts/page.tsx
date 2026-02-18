"use client";

import { useEffect, useState, useCallback } from "react";
import type { PromptVersion, CreatePromptVersionRequest } from "@/types";
import { apiClient } from "@/lib/api-client";

function CreatePromptModal({
  onClose,
  onSaved,
}: {
  onClose: () => void;
  onSaved: () => void;
}) {
  const [version, setVersion] = useState("");
  const [promptTemplate, setPromptTemplate] = useState("");
  const [systemPrompt, setSystemPrompt] = useState("");
  const [categories, setCategories] = useState("");
  const [notes, setNotes] = useState("");
  const [saving, setSaving] = useState(false);
  const [error, setError] = useState("");

  async function handleSubmit(e: React.FormEvent) {
    e.preventDefault();
    setSaving(true);
    setError("");

    try {
      const body: CreatePromptVersionRequest = {
        version,
        prompt_template: promptTemplate,
        system_prompt: systemPrompt,
        intent_categories: categories
          .split("\n")
          .map((c) => c.trim())
          .filter(Boolean),
        notes: notes || null,
      };
      await apiClient.createPromptVersion(body);
      onSaved();
    } catch (err: unknown) {
      setError(err instanceof Error ? err.message : "Failed to create prompt version");
    } finally {
      setSaving(false);
    }
  }

  return (
    <div className="fixed inset-0 bg-black/50 flex items-center justify-center z-50 overflow-y-auto">
      <div className="bg-white rounded-lg shadow-xl w-full max-w-2xl mx-4 my-8 p-6">
        <h2 className="text-lg font-semibold mb-4">Create Prompt Version</h2>

        {error && (
          <div className="mb-4 p-3 bg-red-50 text-red-700 text-sm rounded">{error}</div>
        )}

        <form onSubmit={handleSubmit} className="space-y-4">
          <div>
            <label className="block text-sm font-medium text-gray-700 mb-1">
              Version (e.g. 1.1.0)
            </label>
            <input
              type="text"
              required
              value={version}
              onChange={(e) => setVersion(e.target.value)}
              placeholder="1.1.0"
              className="w-full border rounded px-3 py-2 text-sm"
            />
          </div>

          <div>
            <label className="block text-sm font-medium text-gray-700 mb-1">
              System Prompt
            </label>
            <textarea
              required
              rows={4}
              value={systemPrompt}
              onChange={(e) => setSystemPrompt(e.target.value)}
              className="w-full border rounded px-3 py-2 text-sm font-mono"
            />
          </div>

          <div>
            <label className="block text-sm font-medium text-gray-700 mb-1">
              Prompt Template
            </label>
            <textarea
              required
              rows={6}
              value={promptTemplate}
              onChange={(e) => setPromptTemplate(e.target.value)}
              placeholder="Use {placeholders} for variables"
              className="w-full border rounded px-3 py-2 text-sm font-mono"
            />
          </div>

          <div>
            <label className="block text-sm font-medium text-gray-700 mb-1">
              Intent Categories (one per line)
            </label>
            <textarea
              required
              rows={5}
              value={categories}
              onChange={(e) => setCategories(e.target.value)}
              placeholder={"pricing_discussion\ncontract_negotiation\ntechnical_evaluation"}
              className="w-full border rounded px-3 py-2 text-sm font-mono"
            />
          </div>

          <div>
            <label className="block text-sm font-medium text-gray-700 mb-1">
              Notes
            </label>
            <input
              type="text"
              value={notes}
              onChange={(e) => setNotes(e.target.value)}
              placeholder="Optional change notes"
              className="w-full border rounded px-3 py-2 text-sm"
            />
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
              {saving ? "Creating..." : "Create Version"}
            </button>
          </div>
        </form>
      </div>
    </div>
  );
}

function PromptDiffView({
  left,
  right,
  onClose,
}: {
  left: PromptVersion;
  right: PromptVersion;
  onClose: () => void;
}) {
  return (
    <div className="fixed inset-0 bg-black/50 flex items-center justify-center z-50 overflow-y-auto">
      <div className="bg-white rounded-lg shadow-xl w-full max-w-4xl mx-4 my-8 p-6">
        <div className="flex justify-between items-center mb-4">
          <h2 className="text-lg font-semibold">
            Diff: v{left.version} &rarr; v{right.version}
          </h2>
          <button onClick={onClose} className="text-gray-400 hover:text-gray-600">
            Close
          </button>
        </div>

        <div className="grid grid-cols-2 gap-4">
          <div>
            <h3 className="text-sm font-medium text-gray-500 mb-2">
              v{left.version} - System Prompt
            </h3>
            <pre className="bg-red-50 p-3 rounded text-xs overflow-auto max-h-60">
              {left.system_prompt}
            </pre>
          </div>
          <div>
            <h3 className="text-sm font-medium text-gray-500 mb-2">
              v{right.version} - System Prompt
            </h3>
            <pre className="bg-green-50 p-3 rounded text-xs overflow-auto max-h-60">
              {right.system_prompt}
            </pre>
          </div>

          <div>
            <h3 className="text-sm font-medium text-gray-500 mb-2">
              v{left.version} - Template
            </h3>
            <pre className="bg-red-50 p-3 rounded text-xs overflow-auto max-h-60">
              {left.prompt_template}
            </pre>
          </div>
          <div>
            <h3 className="text-sm font-medium text-gray-500 mb-2">
              v{right.version} - Template
            </h3>
            <pre className="bg-green-50 p-3 rounded text-xs overflow-auto max-h-60">
              {right.prompt_template}
            </pre>
          </div>
        </div>

        <div className="mt-4">
          <h3 className="text-sm font-medium text-gray-500 mb-2">
            Category Changes
          </h3>
          <div className="grid grid-cols-2 gap-4">
            <div className="text-xs">
              {left.intent_categories.map((c) => (
                <div
                  key={c}
                  className={`py-0.5 ${
                    !right.intent_categories.includes(c) ? "text-red-600 font-medium" : ""
                  }`}
                >
                  {!right.intent_categories.includes(c) ? "- " : "  "}
                  {c}
                </div>
              ))}
            </div>
            <div className="text-xs">
              {right.intent_categories.map((c) => (
                <div
                  key={c}
                  className={`py-0.5 ${
                    !left.intent_categories.includes(c) ? "text-green-600 font-medium" : ""
                  }`}
                >
                  {!left.intent_categories.includes(c) ? "+ " : "  "}
                  {c}
                </div>
              ))}
            </div>
          </div>
        </div>
      </div>
    </div>
  );
}

export default function AdminPromptsPage() {
  const [versions, setVersions] = useState<PromptVersion[]>([]);
  const [loading, setLoading] = useState(true);
  const [showCreate, setShowCreate] = useState(false);
  const [diffPair, setDiffPair] = useState<[PromptVersion, PromptVersion] | null>(null);
  const [expandedId, setExpandedId] = useState<string | null>(null);

  const fetchVersions = useCallback(async () => {
    setLoading(true);
    try {
      const data = await apiClient.getPromptVersions();
      setVersions(data.items);
    } catch (err) {
      console.error("Failed to load prompt versions", err);
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    fetchVersions();
  }, [fetchVersions]);

  async function handleActivate(id: string) {
    if (!confirm("Activate this prompt version? The current active version will be deactivated.")) return;
    try {
      await apiClient.activatePromptVersion(id);
      fetchVersions();
    } catch (err) {
      console.error("Failed to activate prompt version", err);
    }
  }

  function handleSaved() {
    setShowCreate(false);
    fetchVersions();
  }

  function showDiff(left: PromptVersion, right: PromptVersion) {
    setDiffPair([left, right]);
  }

  return (
    <div>
      <div className="flex items-center justify-between mb-6">
        <h1 className="text-2xl font-semibold text-gray-900">Prompt Versions</h1>
        <button
          onClick={() => setShowCreate(true)}
          className="px-4 py-2 text-sm bg-blue-600 text-white rounded hover:bg-blue-700"
        >
          Create Version
        </button>
      </div>

      {loading ? (
        <div className="py-12 text-center text-gray-500">Loading...</div>
      ) : (
        <div className="space-y-3">
          {versions.map((v, idx) => (
            <div
              key={v.id}
              className={`bg-white shadow rounded-lg p-4 ${
                v.is_active ? "ring-2 ring-blue-500" : ""
              }`}
            >
              <div className="flex items-center justify-between">
                <div className="flex items-center gap-3">
                  <span className="text-lg font-mono font-medium">v{v.version}</span>
                  {v.is_active && (
                    <span className="px-2 py-0.5 text-xs bg-blue-100 text-blue-800 rounded-full font-medium">
                      Active
                    </span>
                  )}
                  <span className="text-sm text-gray-500">
                    {new Date(v.created_at).toLocaleDateString()}
                  </span>
                  {v.notes && (
                    <span className="text-sm text-gray-500 italic">{v.notes}</span>
                  )}
                </div>
                <div className="flex items-center gap-2">
                  {!v.is_active && (
                    <button
                      onClick={() => handleActivate(v.id)}
                      className="px-3 py-1 text-sm text-blue-600 border border-blue-600 rounded hover:bg-blue-50"
                    >
                      Activate
                    </button>
                  )}
                  {idx < versions.length - 1 && (
                    <button
                      onClick={() => showDiff(versions[idx + 1], v)}
                      className="px-3 py-1 text-sm text-gray-600 border rounded hover:bg-gray-50"
                    >
                      Diff
                    </button>
                  )}
                  <button
                    onClick={() =>
                      setExpandedId(expandedId === v.id ? null : v.id)
                    }
                    className="px-3 py-1 text-sm text-gray-600 border rounded hover:bg-gray-50"
                  >
                    {expandedId === v.id ? "Collapse" : "Expand"}
                  </button>
                </div>
              </div>

              {expandedId === v.id && (
                <div className="mt-4 space-y-3">
                  <div>
                    <h4 className="text-xs font-medium text-gray-500 uppercase mb-1">
                      System Prompt
                    </h4>
                    <pre className="bg-gray-50 p-3 rounded text-xs overflow-auto max-h-40">
                      {v.system_prompt}
                    </pre>
                  </div>
                  <div>
                    <h4 className="text-xs font-medium text-gray-500 uppercase mb-1">
                      Prompt Template
                    </h4>
                    <pre className="bg-gray-50 p-3 rounded text-xs overflow-auto max-h-40">
                      {v.prompt_template}
                    </pre>
                  </div>
                  <div>
                    <h4 className="text-xs font-medium text-gray-500 uppercase mb-1">
                      Intent Categories ({v.intent_categories.length})
                    </h4>
                    <div className="flex flex-wrap gap-1">
                      {v.intent_categories.map((cat) => (
                        <span
                          key={cat}
                          className="px-2 py-0.5 bg-gray-100 text-xs rounded"
                        >
                          {cat}
                        </span>
                      ))}
                    </div>
                  </div>
                </div>
              )}
            </div>
          ))}
        </div>
      )}

      {showCreate && (
        <CreatePromptModal onClose={() => setShowCreate(false)} onSaved={handleSaved} />
      )}

      {diffPair && (
        <PromptDiffView
          left={diffPair[0]}
          right={diffPair[1]}
          onClose={() => setDiffPair(null)}
        />
      )}
    </div>
  );
}
