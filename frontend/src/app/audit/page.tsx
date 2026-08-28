"use client";

import useSWR from "swr";
import { api } from "@/lib/api";

export default function AuditPage() {
  const { data, error } = useSWR("audit", () => api.listAudit());
  return (
    <div className="card p-4">
      <div className="font-semibold mb-2">Audit log</div>
      {error && <div className="text-bad text-sm">{String(error)}</div>}
      <table className="w-full text-sm">
        <thead className="text-muted text-left">
          <tr>
            <th className="py-2">When</th>
            <th>Actor</th>
            <th>Action</th>
            <th>Target</th>
          </tr>
        </thead>
        <tbody>
          {(data ?? []).map((a) => (
            <tr key={a.id} className="border-t border-line">
              <td className="py-2 whitespace-nowrap">{new Date(a.created_at).toLocaleString()}</td>
              <td>{a.actor}</td>
              <td className="font-mono text-xs">{a.action}</td>
              <td className="font-mono text-xs">
                {a.target_type}:{a.target_id}
              </td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}
