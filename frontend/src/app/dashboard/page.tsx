"use client";

import Link from "next/link";
import useSWR from "swr";
import { api } from "@/lib/api";
import { useAuth } from "@/contexts/AuthContext";

export default function DashboardPage() {
  const { user, currentWorkspace } = useAuth();
  const { data: funnel } = useSWR(user ? "dash-funnel" : null, () => api.funnel());
  const { data: report } = useSWR(user ? "dash-weekly" : null, () => api.weeklyReport());
  const { data: approvals } = useSWR(user ? "dash-approvals" : null, () =>
    api.listApprovals("PENDING"),
  );
  const { data: workflows } = useSWR(user ? "dash-workflows" : null, () =>
    api.listWorkflows(),
  );

  const f = (funnel as Record<string, unknown>) || {};
  const ops = ((report as Record<string, unknown> | null)?.operations as Record<string, unknown>) || {};

  const stat = (label: string, value: string, href: string) => (
    <Link
      key={label}
      href={href}
      className="p-4 rounded-2xl bg-[#0e1217] border border-white/[0.08] hover:border-white/[0.16] transition-all"
    >
      <div className="text-[11px] text-muted uppercase tracking-wider">{label}</div>
      <div className="text-xl font-bold text-ink mt-1">{value}</div>
    </Link>
  );

  return (
    <div className="space-y-6">
      <div>
        <h1 className="text-2xl font-bold text-ink">Dashboard</h1>
        <p className="text-xs text-muted mt-1">
          {currentWorkspace ? `${currentWorkspace.name} · ` : ""}Live business overview — real data only.
        </p>
      </div>

      <div className="grid grid-cols-2 lg:grid-cols-4 gap-3">
        {stat("Leads", String(f.leads_total ?? "—"), "/leads")}
        {stat("Meetings", String(f.meetings ?? "—"), "/leads")}
        {stat("Won", String(f.won ?? "—"), "/analytics")}
        {stat("Pending approvals", String(approvals?.length ?? "—"), "/approvals")}
      </div>

      <div className="grid grid-cols-1 lg:grid-cols-2 gap-3">
        <div className="p-5 rounded-2xl bg-[#0e1217] border border-white/[0.08]">
          <div className="text-xs font-semibold text-ink mb-2">Operations</div>
          <div className="text-xs text-muted space-y-1">
            <div>Workflows: {String(ops.workflows ?? workflows?.length ?? "—")}</div>
            <div>Scheduled follow-ups: {String(ops.followups_scheduled ?? "—")}</div>
            <div>Qualified, not contacted: {String(ops.qualified_not_contacted ?? "—")}</div>
          </div>
          <Link href="/analytics" className="text-xs text-accent underline mt-2 inline-block">
            Full analytics →
          </Link>
        </div>
        <div className="p-5 rounded-2xl bg-[#0e1217] border border-white/[0.08]">
          <div className="text-xs font-semibold text-ink mb-2">Recent workflows</div>
          <div className="text-xs text-muted space-y-1">
            {(workflows || []).slice(0, 5).map((w) => (
              <div key={w.id} className="flex justify-between gap-2">
                <span className="truncate">{w.title}</span>
                <span className="font-mono">{w.state}</span>
              </div>
            ))}
            {(!workflows || workflows.length === 0) && <span>No workflows yet.</span>}
          </div>
          <Link href="/workflows" className="text-xs text-accent underline mt-2 inline-block">
            All workflows →
          </Link>
        </div>
      </div>
    </div>
  );
}
