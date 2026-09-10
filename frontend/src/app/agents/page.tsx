"use client";

import useSWR from "swr";
import { useState } from "react";
import { api } from "@/lib/api";
import { useAuth } from "@/contexts/AuthContext";
import type { AgentInfo } from "@/lib/types";

const AGENT_ICONS: Record<string, string> = {
  command: "⚡",
  workflow: "🔁",
  audit: "🔍",
  sales: "🎯",
  marketing: "📢",
  finance: "💳",
  support: "🎧",
  engineering: "💻",
  knowledge: "📚",
  analytics: "📊",
  security: "🛡️",
};

export default function AgentsPage() {
  const { user, openAuthModal } = useAuth();
  const { data: agents, mutate, isLoading } = useSWR(
    user ? "agents" : null,
    () => api.listAgents()
  );

  const [togglingId, setTogglingId] = useState<string | null>(null);

  async function toggleAgent(agent: AgentInfo) {
    setTogglingId(agent.id);
    try {
      await api.setAgentEnabled(agent.id, !agent.enabled);
      await mutate();
    } catch (e) {
      alert((e as Error).message);
    } finally {
      setTogglingId(null);
    }
  }

  if (!user) {
    return (
      <div className="max-w-2xl mx-auto py-12 px-4 text-center">
        <div className="w-16 h-16 mx-auto mb-6 rounded-2xl bg-gradient-to-tr from-accent/20 to-purple-500/20 border border-accent/30 flex items-center justify-center text-2xl shadow-[0_0_30px_rgba(91,141,239,0.2)]">
          🤖
        </div>
        <h1 className="text-2xl font-bold tracking-tight text-ink mb-2">
          Autonomous AI Workforce Directory
        </h1>
        <p className="text-sm text-muted max-w-md mx-auto mb-8">
          Manage, configure, and monitor your 11 specialized autonomous agents. Sign in to toggle permissions and tool configurations.
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
            <span>🤖</span>
            <span>AI Workforce Directory</span>
          </h1>
          <p className="text-xs text-muted mt-0.5">
            Configure agent permissions, view enabled toolsets, and manage autonomy levels.
          </p>
        </div>

        <div className="flex items-center gap-3">
          <span className="text-xs text-muted">
            Total Agents: <strong className="text-ink">{agents?.length ?? 11}</strong>
          </span>
          <button
            onClick={() => mutate()}
            className="px-3 py-1.5 rounded-lg bg-white/5 hover:bg-white/10 border border-white/10 text-xs text-muted hover:text-ink transition-colors"
          >
            Refresh
          </button>
        </div>
      </div>

      {/* Agents Grid */}
      {isLoading ? (
        <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-4">
          {[1, 2, 3, 4, 5, 6].map((i) => (
            <div key={i} className="h-44 rounded-2xl bg-white/[0.02] border border-white/5 animate-pulse" />
          ))}
        </div>
      ) : (
        <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-4">
          {(agents ?? []).map((a) => {
            const iconKey = Object.keys(AGENT_ICONS).find((k) => a.name.toLowerCase().includes(k)) || "command";
            const icon = AGENT_ICONS[iconKey] || "🤖";
            const isBuiltin = a.id.startsWith("builtin:");
            const isToggling = togglingId === a.id;

            return (
              <div
                key={a.id}
                className={`p-5 rounded-2xl border transition-all flex flex-col justify-between ${
                  a.enabled
                    ? "bg-[#0e1217] border-white/[0.08] hover:border-white/[0.16] shadow-sm"
                    : "bg-[#090b0e] border-white/[0.03] opacity-60"
                }`}
              >
                <div>
                  <div className="flex items-start justify-between gap-3 mb-3">
                    <div className="flex items-center gap-3">
                      <div className="w-10 h-10 rounded-xl bg-white/[0.04] border border-white/10 flex items-center justify-center text-lg">
                        {icon}
                      </div>
                      <div>
                        <h2 className="text-sm font-semibold text-ink tracking-tight">
                          {a.name}
                        </h2>
                        <div className="flex items-center gap-1.5 mt-0.5">
                          <span
                            className={`w-1.5 h-1.5 rounded-full ${
                              a.enabled ? "bg-ok animate-pulse" : "bg-muted"
                            }`}
                          />
                          <span className="text-[10px] font-mono text-muted uppercase">
                            {a.enabled ? "Active" : "Disabled"}
                          </span>
                        </div>
                      </div>
                    </div>

                    {/* Enable / Disable Switch */}
                    <button
                      onClick={() => toggleAgent(a)}
                      disabled={isBuiltin || isToggling}
                      title={isBuiltin ? "System built-in agent (configured by workspace admin)" : ""}
                      className={`px-3 py-1 rounded-full text-xs font-medium transition-all ${
                        a.enabled
                          ? "bg-ok/15 text-ok hover:bg-ok/25 border border-ok/30"
                          : "bg-white/5 text-muted hover:text-ink border border-white/10"
                      } ${isBuiltin ? "cursor-not-allowed opacity-80" : ""}`}
                    >
                      {isToggling ? "…" : a.enabled ? "Enabled" : "Enable"}
                    </button>
                  </div>

                  <p className="text-xs text-muted leading-relaxed mb-4 line-clamp-2">
                    {a.description || "Autonomous agent specialized for company operations."}
                  </p>
                </div>

                <div>
                  <div className="text-[10px] font-mono text-muted/70 uppercase mb-1.5">
                    Authorized Tools ({a.allowed_tools?.length ?? 0})
                  </div>
                  <div className="flex flex-wrap gap-1">
                    {a.allowed_tools && a.allowed_tools.length > 0 ? (
                      a.allowed_tools.slice(0, 4).map((tool) => (
                        <span
                          key={tool}
                          className="px-2 py-0.5 rounded-md bg-white/[0.03] border border-white/[0.06] text-[10px] font-mono text-muted"
                        >
                          {tool}
                        </span>
                      ))
                    ) : (
                      <span className="text-[11px] text-muted/60">—</span>
                    )}
                    {a.allowed_tools && a.allowed_tools.length > 4 && (
                      <span className="px-1.5 py-0.5 rounded-md text-[10px] text-muted/60 font-mono">
                        +{a.allowed_tools.length - 4} more
                      </span>
                    )}
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
