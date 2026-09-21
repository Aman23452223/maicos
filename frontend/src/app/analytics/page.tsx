"use client";

import { useEffect, useState } from "react";
import { api } from "@/lib/api";

export default function AnalyticsPage() {
  const [report, setReport] = useState<Record<string, unknown> | null>(null);
  const [err, setErr] = useState<string | null>(null);

  useEffect(() => {
    api.weeklyReport().then((r) => setReport(r)).catch((e) => setErr((e as Error).message));
  }, []);

  const funnel = (report?.funnel as Record<string, unknown>) || null;

  return (
    <div className="space-y-6">
      <div>
        <h1 className="text-2xl font-bold text-ink">Analytics</h1>
        <p className="text-xs text-muted mt-1">Real DB metrics only — actual counts, no estimates.</p>
      </div>
      {err && <div className="text-xs text-bad">{err}</div>}
      {funnel ? (
        <div className="p-5 rounded-2xl bg-[#0e1217] border border-white/[0.08] text-xs space-y-2">
          <div className="text-ink font-semibold">Lead Funnel (actual)</div>
          <div className="text-muted">Total: {String(funnel.leads_total ?? 0)}</div>
          <div className="text-muted">Contacted: {String(funnel.contacted ?? 0)}</div>
          <div className="text-muted">Responded: {String(funnel.responded ?? 0)}</div>
          <div className="text-muted">Meetings: {String(funnel.meetings ?? 0)}</div>
          <div className="text-muted">Won: {String(funnel.won ?? 0)}</div>
          <div className="text-muted">Response rate: {String(funnel.response_rate ?? 0)}</div>
          <div className="text-muted">Conversion rate: {String(funnel.conversion_rate ?? 0)}</div>
        </div>
      ) : (
        <div className="text-xs text-muted">Loading…</div>
      )}
    </div>
  );
}
