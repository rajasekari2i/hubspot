"use client";

import { useEffect, useState, useCallback } from "react";
import type { Deal } from "@/types";
import { apiClient } from "@/lib/api-client";

export default function DealsPage() {
  const [deals, setDeals] = useState<Deal[]>([]);
  const [total, setTotal] = useState(0);
  const [page, setPage] = useState(1);
  const [pageSize] = useState(20);
  const [loading, setLoading] = useState(true);

  const fetchData = useCallback(async () => {
    setLoading(true);
    try {
      const data = await apiClient.getDeals({
        page: String(page),
        page_size: String(pageSize),
      });
      setDeals(data.items);
      setTotal(data.total);
    } catch (err) {
      console.error("Failed to load deals", err);
    } finally {
      setLoading(false);
    }
  }, [page, pageSize]);

  useEffect(() => {
    fetchData();
  }, [fetchData]);

  const totalPages = Math.ceil(total / pageSize);

  return (
    <div>
      <h1 className="text-2xl font-semibold text-gray-900 mb-6">Deals</h1>

      {loading ? (
        <div className="py-12 text-center text-gray-500">Loading...</div>
      ) : (
        <div className="bg-white shadow rounded-lg overflow-hidden">
          <table className="min-w-full divide-y divide-gray-200">
            <thead className="bg-gray-50">
              <tr>
                <th className="px-4 py-3 text-left text-xs font-medium text-gray-500 uppercase">
                  Deal Name
                </th>
                <th className="px-4 py-3 text-left text-xs font-medium text-gray-500 uppercase">
                  Pipeline
                </th>
                <th className="px-4 py-3 text-left text-xs font-medium text-gray-500 uppercase">
                  Stage
                </th>
                <th className="px-4 py-3 text-left text-xs font-medium text-gray-500 uppercase">
                  Owner
                </th>
                <th className="px-4 py-3 text-left text-xs font-medium text-gray-500 uppercase">
                  Amount
                </th>
                <th className="px-4 py-3 text-left text-xs font-medium text-gray-500 uppercase">
                  Threads
                </th>
                <th className="px-4 py-3 text-left text-xs font-medium text-gray-500 uppercase">
                  Recommendations
                </th>
                <th className="px-4 py-3 text-left text-xs font-medium text-gray-500 uppercase">
                  Last Synced
                </th>
              </tr>
            </thead>
            <tbody className="divide-y divide-gray-200">
              {deals.map((deal) => (
                <tr key={deal.id} className="hover:bg-gray-50">
                  <td className="px-4 py-3 text-sm font-medium text-gray-900">
                    <a
                      href={`/dashboard/deals/${deal.id}`}
                      className="hover:text-blue-600"
                    >
                      {deal.deal_name}
                    </a>
                  </td>
                  <td className="px-4 py-3 text-sm text-gray-600">
                    {deal.pipeline_name}
                  </td>
                  <td className="px-4 py-3 text-sm text-gray-600">
                    {deal.current_stage_name}
                  </td>
                  <td className="px-4 py-3 text-sm text-gray-600">
                    {deal.owner?.display_name || "-"}
                  </td>
                  <td className="px-4 py-3 text-sm text-gray-600">
                    {deal.amount
                      ? `$${Number(deal.amount).toLocaleString()}`
                      : "-"}
                  </td>
                  <td className="px-4 py-3 text-sm text-center text-gray-600">
                    {deal.thread_count}
                  </td>
                  <td className="px-4 py-3 text-sm text-center text-gray-600">
                    {deal.recommendation_count}
                  </td>
                  <td className="px-4 py-3 text-sm text-gray-500">
                    {deal.last_synced_at
                      ? new Date(deal.last_synced_at).toLocaleDateString()
                      : "-"}
                  </td>
                </tr>
              ))}
            </tbody>
          </table>

          {totalPages > 1 && (
            <div className="flex items-center justify-between px-4 py-3 bg-gray-50">
              <span className="text-sm text-gray-700">
                {total} total deals
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
