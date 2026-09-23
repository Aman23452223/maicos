"use client";

import Link from "next/link";
import useSWR from "swr";
import { api } from "@/lib/api";
import { useAuth } from "@/contexts/AuthContext";

export default function StartupOverview() {
  const { user } = useAuth();
  const { data } = useSWR(user ? "startup-status" : null, () => api.startupStatus());

  const stages = data?.stages || {};
  return (
    <div className="space-y-6">
      <div>
        <h1 className="text-2xl font-bold text-ink">🚀 Startup Builder</h1>
        <p className="text-xs text-muted mt-1">
          Idea → launch → operations. Readiness is computed from real workspace state — never invented.
        </p>
      </div>

      <div className="p-5 rounded-2xl bg-[#0e1217] border border-white/[0.08]">
        <div className="flex items-center justify-between mb-2">
          <div className="text-xs font-semibold text-ink">Launch Readiness</div>
          <div className="text-sm font-bold text-ink">{data?.readiness ?? 0}%</div>
        </div>
        <div className="h-2 rounded-full bg-white/5 overflow-hidden">
          <div className="h-full bg-accent transition-all" style={{ width: `${data?.readiness ?? 0}%` }} />
        </div>
        <div className="text-[11px] text-muted mt-1">
          {data?.done ?? 0} of {data?.total ?? 0} stages complete
        </div>
      </div>

      <div className="grid grid-cols-1 md:grid-cols-2 gap-3">
        {Object.entries(stages).map(([name, s]) => (
          <div key={name} className="p-4 rounded-xl bg-[#0e1217] border border-white/[0.08] flex items-center justify-between">
            <div>
              <div className="text-xs font-semibold text-ink capitalize">{name}</div>
              <div className="text-[11px] text-muted">{s.detail}</div>
            </div>
            <span className={`text-xs font-bold ${s.done ? "text-ok" : "text-muted"}`}>
              {s.done ? "✓" : "○"}
            </span>
          </div>
        ))}
      </div>

      <div className="flex flex-wrap gap-2">
        <Link href="/startup/idea" className="px-4 py-2 rounded-xl bg-accent text-bg text-xs font-semibold">
          1. Describe idea
        </Link>
        <Link href="/startup/blueprint" className="px-4 py-2 rounded-xl bg-white/5 border border-white/10 text-xs">
          2. Blueprint
        </Link>
        <Link href="/startup/projects" className="px-4 py-2 rounded-xl bg-white/5 border border-white/10 text-xs">
          3. Projects & roles
        </Link>
        <Link href="/startup/launch" className="px-4 py-2 rounded-xl bg-white/5 border border-white/10 text-xs">
          4. Launch
        </Link>
      </div>
    </div>
  );
}
