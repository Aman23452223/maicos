"use client";

import useSWR from "swr";
import { api } from "@/lib/api";
import { useAuth } from "@/contexts/AuthContext";

const CONNECTOR_METAS: Record<string, { icon: string; desc: string; category: string }> = {
  slack: { icon: "💬", desc: "Send notifications, post messages & listen to commands.", category: "Comms" },
  stripe: { icon: "💳", desc: "Manage billing, verify customer invoices & handle payments.", category: "Finance" },
  hubspot: { icon: "🎯", desc: "Synchronize leads, contacts, deals & outreach pipelines.", category: "Sales" },
  postgres: { icon: "🐘", desc: "Read and write company business database entities.", category: "Data" },
  github: { icon: "🐙", desc: "Pull request reviews, issue management & repository stats.", category: "Dev" },
  gmail: { icon: "✉️", desc: "Draft and dispatch autonomous email sequences.", category: "Comms" },
  linear: { icon: "📐", desc: "Track engineering tickets, sprints & feature roadmaps.", category: "Product" },
};

export default function IntegrationsPage() {
  const { user, openAuthModal } = useAuth();
  const { data: tools, error, mutate, isLoading } = useSWR(
    user ? "tools" : null,
    () => api.listTools()
  );

  if (!user) {
    return (
      <div className="max-w-2xl mx-auto py-12 px-4 text-center">
        <div className="w-16 h-16 mx-auto mb-6 rounded-2xl bg-gradient-to-tr from-accent/20 to-purple-500/20 border border-accent/30 flex items-center justify-center text-2xl shadow-[0_0_30px_rgba(91,141,239,0.2)]">
          🔌
        </div>
        <h1 className="text-2xl font-bold tracking-tight text-ink mb-2">
          Enterprise Integrations Hub
        </h1>
        <p className="text-sm text-muted max-w-md mx-auto mb-8">
          Connect MAICOS to Slack, Stripe, GitHub, PostgreSQL, and CRM providers. Sign in to view and configure connector credentials.
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
            <span>🔌</span>
            <span>Integrations & Connectors</span>
          </h1>
          <p className="text-xs text-muted mt-0.5">
            Active tool connectors that autonomous agents can invoke with permission.
          </p>
        </div>

        <button
          onClick={() => mutate()}
          className="px-3 py-1.5 rounded-lg bg-white/5 hover:bg-white/10 border border-white/10 text-xs text-muted hover:text-ink transition-colors self-start sm:self-auto"
        >
          Refresh Connectors
        </button>
      </div>

      {/* Connectors Grid */}
      {isLoading ? (
        <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-4">
          {[1, 2, 3, 4, 5, 6].map((i) => (
            <div key={i} className="h-44 rounded-2xl bg-white/[0.02] border border-white/5 animate-pulse" />
          ))}
        </div>
      ) : (
        <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-4">
          {(tools ?? []).map((t) => {
            const meta = CONNECTOR_METAS[t.connector.toLowerCase()] || {
              icon: "🔌",
              desc: "External API integration adapter.",
              category: "Tool",
            };

            return (
              <div
                key={t.id}
                className="p-5 rounded-2xl bg-[#0e1217] border border-white/[0.08] hover:border-white/[0.16] transition-all flex flex-col justify-between shadow-sm"
              >
                <div>
                  <div className="flex items-start justify-between gap-3 mb-3">
                    <div className="flex items-center gap-3">
                      <div className="w-10 h-10 rounded-xl bg-white/[0.04] border border-white/10 flex items-center justify-center text-lg">
                        {meta.icon}
                      </div>
                      <div>
                        <h2 className="text-sm font-semibold text-ink font-mono uppercase tracking-wider">
                          {t.connector}
                        </h2>
                        <span className="text-[10px] px-2 py-0.2 rounded-full bg-white/5 text-muted border border-white/5">
                          {meta.category}
                        </span>
                      </div>
                    </div>

                    <span
                      className={`px-2 py-0.5 rounded-full text-[10px] font-bold uppercase tracking-wider ${
                        t.enabled
                          ? "bg-ok/10 text-ok border border-ok/20"
                          : "bg-white/5 text-muted border border-white/10"
                      }`}
                    >
                      {t.enabled ? "Active" : "Disabled"}
                    </span>
                  </div>

                  <p className="text-xs text-muted leading-relaxed mb-4">
                    {meta.desc}
                  </p>
                </div>

                <div>
                  <div className="text-[10px] font-mono text-muted/70 uppercase mb-1.5">
                    Operations
                  </div>
                  <div className="flex flex-wrap gap-1">
                    {t.operations.map((op) => (
                      <span
                        key={op}
                        className="px-2 py-0.5 rounded-md bg-white/[0.03] border border-white/[0.06] text-[10px] font-mono text-accent"
                      >
                        {op}
                      </span>
                    ))}
                  </div>
                </div>
              </div>
            );
          })}
        </div>
      )}
    </div>
  );
}
