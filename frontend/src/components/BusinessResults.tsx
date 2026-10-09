"use client";

import { useState } from "react";
import useSWR from "swr";
import { api } from "@/lib/api";
import { useAuth } from "@/contexts/AuthContext";

/** Business Results: per-client rows + reconciled summary, read straight
 * from persisted records (GET /v1/reports/clients). Rendered only from
 * API data — nothing invented. Refresh-safe (SWR refetch) and printable.
 */
export function BusinessResults() {
  const { user } = useAuth();
  const [collapsed, setCollapsed] = useState(false);
  const { data, error, mutate } = useSWR(user ? "clients-report" : null, () =>
    api.clientsReport()
  );

  if (!user) return null;

  const summary = data?.summary;
  const clients = data?.clients ?? [];

  return (
    <div
      id="business-results"
      className="p-5 rounded-2xl bg-[#0e1217] border border-white/[0.08] shadow-lg space-y-4"
    >
      <div className="flex items-center justify-between">
        <h3 className="text-sm font-semibold text-ink flex items-center gap-2">
          <span>📊</span>
          <span>Business Results</span>
        </h3>
        <div className="flex items-center gap-2">
          <button
            onClick={() => window.print()}
            className="px-3 py-1.5 rounded-lg bg-white/5 hover:bg-white/10 border border-white/10 text-xs text-muted hover:text-ink transition-colors"
            title="Print this report"
          >
            🖨️ Print
          </button>
          <button
            onClick={() => {
              setCollapsed(!collapsed);
              if (collapsed) mutate();
            }}
            className="px-3 py-1.5 rounded-lg bg-white/5 hover:bg-white/10 border border-white/10 text-xs text-muted hover:text-ink transition-colors"
          >
            {collapsed ? "Expand ▸" : "Collapse ▾"}
          </button>
        </div>
      </div>

      {error && (
        <p className="text-xs text-bad">Could not load report: {(error as Error).message}</p>
      )}
      {!data && !error && (
        <p className="text-xs text-muted font-mono">Loading business results…</p>
      )}

      {!collapsed && data && (
        <>
          {summary && (
            <div className="flex flex-wrap gap-2 text-[11px]">
              <SummaryChip label="CRM records" value={summary.crm_records} />
              <SummaryChip label="Scored" value={summary.scored} />
              <SummaryChip label="Qualified" value={summary.qualified} tone="ok" />
              <SummaryChip label="Nurtured" value={summary.nurtured} />
              <SummaryChip label="Disqualified" value={summary.disqualified} />
              <SummaryChip label="Follow-ups scheduled" value={summary.followups_scheduled} tone="ok" />
            </div>
          )}

          <div className="overflow-x-auto">
            <table className="w-full text-xs text-left">
              <thead className="text-muted border-b border-white/[0.08]">
                <tr>
                  <th className="py-2 font-medium">Client</th>
                  <th className="font-medium">Status</th>
                  <th className="font-medium">Score</th>
                  <th className="font-medium">Priority</th>
                  <th className="font-medium">Decision & reason</th>
                  <th className="font-medium">Next action</th>
                  <th className="font-medium">Follow-ups</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-white/5">
                {clients.map((c) => (
                  <tr key={c.lead_id} className="hover:bg-white/[0.02] align-top">
                    <td className="py-2.5 pr-3">
                      <div className="font-medium text-ink">{c.name}</div>
                      <div className="text-[10px] text-muted font-mono break-all" title={c.lead_id}>
                        {c.email || "no email"} · {c.lead_id.slice(0, 8)}…
                      </div>
                    </td>
                    <td>
                      <span className="px-2 py-0.5 rounded-full text-[10px] font-bold uppercase bg-white/5 text-muted">
                        {c.status}
                      </span>
                    </td>
                    <td className="font-mono">{c.score}</td>
                    <td className="font-mono">{c.priority}</td>
                    <td className="max-w-xs">
                      <div className="font-medium text-ink">{c.decision}</div>
                      <div className="text-[11px] text-muted">{c.reason}</div>
                      {c.requirements_note && (
                        <div className="text-[11px] text-muted/80 italic">
                          “{c.requirements_note.slice(0, 120)}”
                        </div>
                      )}
                    </td>
                    <td className="max-w-xs text-[11px] text-ink/85">{c.next_action}</td>
                    <td className="text-[11px] font-mono">
                      {c.followups_scheduled > 0 ? (
                        <div className="space-y-0.5">
                          <div className="text-ok">{c.followups_scheduled} scheduled</div>
                          {c.next_due_at && (
                            <div className="text-muted">
                              next: {new Date(c.next_due_at).toLocaleDateString()}
                            </div>
                          )}
                          {c.followup_ids.slice(0, 2).map((id) => (
                            <div key={id} className="text-accent break-all" title={id}>
                              {id.slice(0, 8)}…
                            </div>
                          ))}
                          {c.followup_ids.length > 2 && (
                            <div className="text-muted">+{c.followup_ids.length - 2} more</div>
                          )}
                        </div>
                      ) : (
                        <span className="text-muted">none</span>
                      )}
                    </td>
                  </tr>
                ))}
                {clients.length === 0 && (
                  <tr>
                    <td colSpan={7} className="py-4 text-center text-muted">
                      No CRM records yet — import leads to populate this report.
                    </td>
                  </tr>
                )}
              </tbody>
            </table>
          </div>
        </>
      )}
    </div>
  );
}

function SummaryChip({
  label,
  value,
  tone,
}: {
  label: string;
  value: number | string;
  tone?: "ok";
}) {
  return (
    <span
      className={`px-2.5 py-1 rounded-full font-mono border ${
        tone === "ok"
          ? "bg-ok/10 text-ok border-ok/20"
          : "bg-white/[0.04] text-muted border-white/10"
      }`}
    >
      {label}: {value}
    </span>
  );
}
