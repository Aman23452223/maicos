"use client";

import useSWR from "swr";
import { api } from "@/lib/api";

export default function AgentsPage() {
  const { data, error, mutate } = useSWR("agents", () => api.listAgents());
  async function toggle(id: string, enabled: boolean) {
    try {
      await api.setAgentEnabled(id, enabled);
      await mutate();
    } catch (e) {
      alert((e as Error).message);
    }
  }
  return (
    <div className="card p-4">
      <div className="font-semibold mb-2">Agents</div>
      {error && <div className="text-bad text-sm">{String(error)}</div>}
      <table className="w-full text-sm">
        <thead className="text-muted text-left">
          <tr>
            <th className="py-2">Name</th>
            <th>Description</th>
            <th>Allowed tools</th>
            <th>Status</th>
          </tr>
        </thead>
        <tbody>
          {(data ?? []).map((a) => (
            <tr key={a.id} className="border-t border-line">
              <td className="py-2 font-mono">{a.name}</td>
              <td>{a.description}</td>
              <td className="text-xs">
                {a.allowed_tools.length ? a.allowed_tools.join(", ") : "—"}
              </td>
              <td>
                <button
                  className={a.enabled ? "btn-ghost" : "btn"}
                  onClick={() => toggle(a.id, !a.enabled)}
                  disabled={a.id.startsWith("builtin:")}
                  title={
                    a.id.startsWith("builtin:")
                      ? "Built-in agents are configured by the workspace admin"
                      : ""
                  }
                >
                  {a.enabled ? "Enabled" : "Disabled"}
                </button>
              </td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}
