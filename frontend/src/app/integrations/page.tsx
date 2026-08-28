"use client";

import useSWR from "swr";
import { api } from "@/lib/api";

export default function IntegrationsPage() {
  const { data, error } = useSWR("tools", () => api.listTools());
  return (
    <div className="card p-4">
      <div className="font-semibold mb-2">Integrations</div>
      {error && <div className="text-bad text-sm">{String(error)}</div>}
      <table className="w-full text-sm">
        <thead className="text-muted text-left">
          <tr>
            <th className="py-2">Connector</th>
            <th>Operations</th>
            <th>Enabled</th>
          </tr>
        </thead>
        <tbody>
          {(data ?? []).map((t) => (
            <tr key={t.id} className="border-t border-line">
              <td className="py-2 font-mono">{t.connector}</td>
              <td className="text-xs">{t.operations.join(", ")}</td>
              <td>{t.enabled ? "✓" : "—"}</td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}
