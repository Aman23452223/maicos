"use client";

import { useEffect, useState } from "react";
import { api } from "@/lib/api";
import { statePillClass } from "@/lib/ui";

export default function ApprovalsPage() {
  const [items, setItems] = useState<Awaited<ReturnType<typeof api.listApprovals>>>([]);
  const [err, setErr] = useState<string | null>(null);

  async function refresh() {
    try {
      setItems(await api.listApprovals());
    } catch (e) {
      setErr((e as Error).message);
    }
  }

  useEffect(() => {
    refresh();
  }, []);

  async function decide(id: string, d: "APPROVE" | "REJECT") {
    setErr(null);
    try {
      await api.decide(id, d);
      await refresh();
    } catch (e) {
      setErr((e as Error).message);
    }
  }

  return (
    <div className="card p-4">
      <div className="font-semibold mb-2">Approval center</div>
      {err && <div className="text-bad text-sm mb-2">{err}</div>}
      {items.length === 0 ? (
        <div className="text-muted text-sm">No approvals.</div>
      ) : (
        <table className="w-full text-sm">
          <thead className="text-muted text-left">
            <tr>
              <th className="py-2">Action</th>
              <th>Target</th>
              <th>Requested by</th>
              <th>Description</th>
              <th>Status</th>
              <th>Decision</th>
            </tr>
          </thead>
          <tbody>
            {items.map((a) => (
              <tr key={a.id} className="border-t border-line align-top">
                <td className="py-2">{a.action}</td>
                <td>{a.target_system}</td>
                <td>{a.requested_by_agent}</td>
                <td className="max-w-md">{a.description}</td>
                <td>
                  <span className={statePillClass(a.status)}>{a.status}</span>
                </td>
                <td>
                  {a.status === "PENDING" ? (
                    <div className="flex gap-2">
                      <button className="btn" onClick={() => decide(a.id, "APPROVE")}>
                        Approve
                      </button>
                      <button
                        className="btn-ghost"
                        onClick={() => decide(a.id, "REJECT")}
                      >
                        Reject
                      </button>
                    </div>
                  ) : (
                    <span className="text-muted">—</span>
                  )}
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      )}
    </div>
  );
}
