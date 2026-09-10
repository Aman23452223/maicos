"use client";

import useSWR from "swr";
import { api } from "@/lib/api";
import { useAuth } from "@/contexts/AuthContext";

export default function AuditPage() {
  const { user, openAuthModal } = useAuth();
  const { data: events, error, mutate, isLoading } = useSWR(
    user ? "audit" : null,
    () => api.listAudit()
  );

  if (!user) {
    return (
      <div className="max-w-2xl mx-auto py-12 px-4 text-center">
        <div className="w-16 h-16 mx-auto mb-6 rounded-2xl bg-gradient-to-tr from-accent/20 to-purple-500/20 border border-accent/30 flex items-center justify-center text-2xl shadow-[0_0_30px_rgba(91,141,239,0.2)]">
          📜
        </div>
        <h1 className="text-2xl font-bold tracking-tight text-ink mb-2">
          Enterprise Security Audit Log
        </h1>
        <p className="text-sm text-muted max-w-md mx-auto mb-8">
          Every decision, model generation, API trigger, and approval is cryptographically logged for full compliance and governance. Sign in to inspect logs.
        </p>
        <div className="flex flex-col sm:flex-row items-center justify-center gap-3">
          <button
            onClick={() => openAuthModal("signin")}
            className="w-full sm:w-auto px-6 py-2.5 rounded-xl bg-accent hover:bg-accent/90 text-bg font-semibold text-sm shadow-[0_0_20px_rgba(91,141,239,0.4)] transition-all"
          >
            Sign in to Workspace
          </button>
          <button
            onClick={() => openAuthModal("signup")}
            className="w-full sm:w-auto px-6 py-2.5 rounded-xl bg-white/5 hover:bg-white/10 text-ink border border-white/10 text-sm font-medium transition-all"
          >
            Create Workspace Account
          </button>
        </div>
      </div>
    );
  }

  return (
    <div className="space-y-6">
      {/* Header */}
      <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-4">
        <div>
          <h1 className="text-xl font-bold tracking-tight text-ink flex items-center gap-2">
            <span>📜</span>
            <span>Security & Compliance Audit Trail</span>
          </h1>
          <p className="text-xs text-muted mt-0.5">
            Append-only record of all autonomous decisions, tool actions, and human approvals.
          </p>
        </div>

        <button
          onClick={() => mutate()}
          className="px-3 py-1.5 rounded-lg bg-white/5 hover:bg-white/10 border border-white/10 text-xs text-muted hover:text-ink transition-colors self-start sm:self-auto"
        >
          Refresh Events
        </button>
      </div>

      {/* Audit Events Table */}
      <div className="rounded-2xl bg-[#0e1217] border border-white/[0.08] shadow-lg overflow-hidden">
        {isLoading ? (
          <div className="p-8 text-center text-xs text-muted">
            Loading immutable audit events…
          </div>
        ) : !events || events.length === 0 ? (
          <div className="p-12 text-center text-xs text-muted">
            No audit events recorded in this workspace yet.
          </div>
        ) : (
          <div className="overflow-x-auto">
            <table className="w-full text-xs text-left">
              <thead className="bg-white/[0.02] text-muted border-b border-white/[0.06]">
                <tr>
                  <th className="py-3 px-4 font-medium">Timestamp (UTC)</th>
                  <th className="font-medium px-4">Actor</th>
                  <th className="font-medium px-4">Action</th>
                  <th className="font-medium px-4">Target Entity</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-white/5">
                {events.map((e) => (
                  <tr key={e.id} className="hover:bg-white/[0.02]">
                    <td className="py-3 px-4 text-muted font-mono text-[11px] whitespace-nowrap">
                      {new Date(e.created_at).toLocaleString()}
                    </td>
                    <td className="px-4 font-semibold text-ink">
                      {e.actor}
                    </td>
                    <td className="px-4">
                      <span className="px-2 py-0.5 rounded-md bg-accent/10 border border-accent/20 text-accent font-mono text-[11px]">
                        {e.action}
                      </span>
                    </td>
                    <td className="px-4 font-mono text-muted text-[11px]">
                      {e.target_type}:{e.target_id ? e.target_id.slice(0, 8) : "—"}
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}
      </div>
    </div>
  );
}
