"use client";

import { useEffect, useState, useCallback } from "react";
import type { UserConfig, UserRole, CreateUserRequest, UpdateUserRequest } from "@/types";
import { apiClient } from "@/lib/api-client";

const ROLES: { value: UserRole; label: string }[] = [
  { value: "admin", label: "Admin" },
  { value: "revops", label: "RevOps" },
  { value: "sales_user", label: "Sales User" },
];

function UserFormModal({
  user,
  onClose,
  onSaved,
}: {
  user: UserConfig | null;
  onClose: () => void;
  onSaved: () => void;
}) {
  const isEdit = !!user;
  const [email, setEmail] = useState(user?.email ?? "");
  const [displayName, setDisplayName] = useState(user?.display_name ?? "");
  const [role, setRole] = useState<UserRole>(user?.role ?? "sales_user");
  const [hubspotOwnerId, setHubspotOwnerId] = useState(user?.hubspot_owner_id ?? "");
  const [slackUserId, setSlackUserId] = useState(user?.slack_user_id ?? "");
  const [saving, setSaving] = useState(false);
  const [error, setError] = useState("");

  async function handleSubmit(e: React.FormEvent) {
    e.preventDefault();
    setSaving(true);
    setError("");

    try {
      if (isEdit) {
        const body: UpdateUserRequest = {
          display_name: displayName,
          role,
          hubspot_owner_id: hubspotOwnerId || undefined,
          slack_user_id: slackUserId || undefined,
        };
        await apiClient.updateUser(user.id, body);
      } else {
        const body: CreateUserRequest = {
          email,
          display_name: displayName,
          role,
          hubspot_owner_id: hubspotOwnerId || null,
          slack_user_id: slackUserId || null,
        };
        await apiClient.createUser(body);
      }
      onSaved();
    } catch (err: unknown) {
      setError(err instanceof Error ? err.message : "Failed to save user");
    } finally {
      setSaving(false);
    }
  }

  return (
    <div className="fixed inset-0 bg-black/50 flex items-center justify-center z-50">
      <div className="bg-white rounded-lg shadow-xl w-full max-w-md mx-4 p-6">
        <h2 className="text-lg font-semibold mb-4">
          {isEdit ? "Edit User" : "Add User"}
        </h2>

        {error && (
          <div className="mb-4 p-3 bg-red-50 text-red-700 text-sm rounded">{error}</div>
        )}

        <form onSubmit={handleSubmit} className="space-y-4">
          <div>
            <label className="block text-sm font-medium text-gray-700 mb-1">Email</label>
            <input
              type="email"
              required
              disabled={isEdit}
              value={email}
              onChange={(e) => setEmail(e.target.value)}
              className="w-full border rounded px-3 py-2 text-sm disabled:bg-gray-100"
            />
          </div>

          <div>
            <label className="block text-sm font-medium text-gray-700 mb-1">
              Display Name
            </label>
            <input
              type="text"
              required
              value={displayName}
              onChange={(e) => setDisplayName(e.target.value)}
              className="w-full border rounded px-3 py-2 text-sm"
            />
          </div>

          <div>
            <label className="block text-sm font-medium text-gray-700 mb-1">Role</label>
            <select
              value={role}
              onChange={(e) => setRole(e.target.value as UserRole)}
              className="w-full border rounded px-3 py-2 text-sm"
            >
              {ROLES.map((r) => (
                <option key={r.value} value={r.value}>
                  {r.label}
                </option>
              ))}
            </select>
          </div>

          <div>
            <label className="block text-sm font-medium text-gray-700 mb-1">
              HubSpot Owner ID
            </label>
            <input
              type="text"
              value={hubspotOwnerId}
              onChange={(e) => setHubspotOwnerId(e.target.value)}
              placeholder="Optional"
              className="w-full border rounded px-3 py-2 text-sm"
            />
          </div>

          <div>
            <label className="block text-sm font-medium text-gray-700 mb-1">
              Slack User ID
            </label>
            <input
              type="text"
              value={slackUserId}
              onChange={(e) => setSlackUserId(e.target.value)}
              placeholder="Optional"
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
              {saving ? "Saving..." : isEdit ? "Update" : "Create"}
            </button>
          </div>
        </form>
      </div>
    </div>
  );
}

export default function AdminUsersPage() {
  const [users, setUsers] = useState<UserConfig[]>([]);
  const [loading, setLoading] = useState(true);
  const [editUser, setEditUser] = useState<UserConfig | null>(null);
  const [showForm, setShowForm] = useState(false);

  const fetchUsers = useCallback(async () => {
    setLoading(true);
    try {
      const data = await apiClient.getUsers();
      setUsers(data.items);
    } catch (err) {
      console.error("Failed to load users", err);
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    fetchUsers();
  }, [fetchUsers]);

  async function handleDeactivate(user: UserConfig) {
    if (!confirm(`Deactivate ${user.display_name}?`)) return;
    try {
      await apiClient.updateUser(user.id, { is_active: false });
      fetchUsers();
    } catch (err) {
      console.error("Failed to deactivate user", err);
    }
  }

  async function handleReactivate(user: UserConfig) {
    try {
      await apiClient.updateUser(user.id, { is_active: true });
      fetchUsers();
    } catch (err) {
      console.error("Failed to reactivate user", err);
    }
  }

  function openCreate() {
    setEditUser(null);
    setShowForm(true);
  }

  function openEdit(user: UserConfig) {
    setEditUser(user);
    setShowForm(true);
  }

  function handleSaved() {
    setShowForm(false);
    setEditUser(null);
    fetchUsers();
  }

  const roleBadge = (role: UserRole) => {
    const colors: Record<UserRole, string> = {
      admin: "bg-purple-100 text-purple-800",
      revops: "bg-blue-100 text-blue-800",
      sales_user: "bg-green-100 text-green-800",
    };
    return (
      <span className={`px-2 py-0.5 text-xs font-medium rounded-full ${colors[role]}`}>
        {role}
      </span>
    );
  };

  return (
    <div>
      <div className="flex items-center justify-between mb-6">
        <h1 className="text-2xl font-semibold text-gray-900">User Management</h1>
        <button
          onClick={openCreate}
          className="px-4 py-2 text-sm bg-blue-600 text-white rounded hover:bg-blue-700"
        >
          Add User
        </button>
      </div>

      {loading ? (
        <div className="py-12 text-center text-gray-500">Loading...</div>
      ) : (
        <div className="bg-white shadow rounded-lg overflow-hidden">
          <table className="min-w-full divide-y divide-gray-200">
            <thead className="bg-gray-50">
              <tr>
                <th className="px-4 py-3 text-left text-xs font-medium text-gray-500 uppercase">
                  Name
                </th>
                <th className="px-4 py-3 text-left text-xs font-medium text-gray-500 uppercase">
                  Email
                </th>
                <th className="px-4 py-3 text-left text-xs font-medium text-gray-500 uppercase">
                  Role
                </th>
                <th className="px-4 py-3 text-left text-xs font-medium text-gray-500 uppercase">
                  HubSpot
                </th>
                <th className="px-4 py-3 text-left text-xs font-medium text-gray-500 uppercase">
                  Slack
                </th>
                <th className="px-4 py-3 text-left text-xs font-medium text-gray-500 uppercase">
                  Status
                </th>
                <th className="px-4 py-3 text-right text-xs font-medium text-gray-500 uppercase">
                  Actions
                </th>
              </tr>
            </thead>
            <tbody className="divide-y divide-gray-200">
              {users.map((user) => (
                <tr key={user.id} className="hover:bg-gray-50">
                  <td className="px-4 py-3 text-sm font-medium text-gray-900">
                    {user.display_name}
                  </td>
                  <td className="px-4 py-3 text-sm text-gray-600">{user.email}</td>
                  <td className="px-4 py-3 text-sm">{roleBadge(user.role)}</td>
                  <td className="px-4 py-3 text-sm text-gray-600">
                    {user.hubspot_owner_id || "-"}
                  </td>
                  <td className="px-4 py-3 text-sm text-gray-600">
                    {user.slack_user_id || "-"}
                  </td>
                  <td className="px-4 py-3 text-sm">
                    {user.is_active ? (
                      <span className="text-green-600 font-medium">Active</span>
                    ) : (
                      <span className="text-gray-400">Inactive</span>
                    )}
                  </td>
                  <td className="px-4 py-3 text-sm text-right space-x-2">
                    <button
                      onClick={() => openEdit(user)}
                      className="text-blue-600 hover:text-blue-800"
                    >
                      Edit
                    </button>
                    {user.is_active ? (
                      <button
                        onClick={() => handleDeactivate(user)}
                        className="text-red-600 hover:text-red-800"
                      >
                        Deactivate
                      </button>
                    ) : (
                      <button
                        onClick={() => handleReactivate(user)}
                        className="text-green-600 hover:text-green-800"
                      >
                        Reactivate
                      </button>
                    )}
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}

      {showForm && (
        <UserFormModal
          user={editUser}
          onClose={() => setShowForm(false)}
          onSaved={handleSaved}
        />
      )}
    </div>
  );
}
