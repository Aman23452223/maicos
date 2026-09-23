"use client";

import useSWR from "swr";
import Link from "next/link";
import { api } from "@/lib/api";
import { useAuth } from "@/contexts/AuthContext";

export default function StartupLaunch() {
  const { user } = useAuth();
  const { data: status } = useSWR(user ? "startup-launch-status" : null, () => api.startupStatus());
  const { data: integ } = useSWR(user ? "startup-launch-integ" : null, () => api.integrationCatalog());

  const connected = (integ?.integrations || []).filter((i) => i.status === "connected");
  const readiness = status?.readiness ?? 0;

  return (
    <div className="space-y-6">
      <div>
        <h1 className="text-2xl font-bold text-ink">🚀 Launch Center</h1>
        <p className="text-xs text-muted mt-1">Launch readiness {readiness}% — computed from real state, never invented.</p>
      </div>

      <div className="p-5 rounded-2xl bg-[#0e1217] border border-white/[0.08] space-y-2 text-xs">
        <div className="font-semibold text-ink">Pre-launch checklist</div>
        {[
          { label: "Blueprint approved & applied", done: (status?.stages?.plan?.done || status?.stages?.strategy?.done) || false },
          { label: "Projects created", done: status?.stages?.build?.done || false },
          { label: "Supply/partner motion started", done: status?.stages?.supply?.done || false },
          { label: "Leads flowing", done: status?.stages?.acquire?.done || false },
          { label: `Infrastructure connected (${connected.length})`, done: connected.length > 0 },
        ].map((c) => (
          <div key={c.label} className="flex items-center gap-2 text-muted">
            <span className={c.done ? "text-ok" : ""}>{c.done ? "✓" : "○"}</span> {c.label}
          </div>
        ))}
      </div>

      <div className="flex gap-2">
        <Link href="/startup/projects" className="px-4 py-2 rounded-xl bg-white/5 border border-white/10 text-xs">Workforce</Link>
        <Link href="/integrations" className="px-4 py-2 rounded-xl bg-white/5 border border-white/10 text-xs">Connect infrastructure</Link>
        <Link href="/command" className="px-4 py-2 rounded-xl bg-accent text-bg text-xs font-semibold">Ask MAICOS to launch</Link>
      </div>
    </div>
  );
}
