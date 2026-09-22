"use client";

import useSWR from "swr";
import { useState } from "react";
import { api } from "@/lib/api";
import { useAuth } from "@/contexts/AuthContext";

const ICONS: Record<string, string> = {
  zomato: "🍽️",
  whatsapp: "💬",
  google_calendar: "📅",
  google_sheets: "📊",
  email_smtp: "✉️",
  email_sendgrid: "📧",
  instagram_meta: "📸",
  crm_hubspot: "🎯",
  search_tavily: "🔍",
};

export default function IntegrationsPage() {
  const { user, openAuthModal, currentWorkspace } = useAuth();
  const [busy, setBusy] = useState<string | null>(null);
  const [msg, setMsg] = useState<string | null>(null);
  const { data, error, mutate, isLoading } = useSWR(
    user ? "integration-catalog" : null,
    () => api.integrationCatalog(),
  );

  async function handleConnect(provider: string) {
    setBusy(provider);
    setMsg(null);
    try {
      const r = await api.connectIntegration(provider, currentWorkspace?.name);
      setMsg(
        r.status === "connected"
          ? `${provider} connected.`
          : `${provider}: ${r.detail || "Configuration required."}`,
      );
      mutate();
    } catch (e) {
      setMsg((e as Error).message);
    } finally {
      setBusy(null);
    }
  }

  async function handleDisconnect(provider: string) {
    setBusy(provider);
    try {
      await api.disconnectIntegration(provider);
      mutate();
    } catch (e) {
      setMsg((e as Error).message);
    } finally {
      setBusy(null);
    }
  }

  if (!user) {
    return (
      <div className="max-w-2xl mx-auto py-12 px-4 text-center">
        <h1 className="text-2xl font-bold text-ink mb-2">Integrations</h1>
        <p className="text-sm text-muted mb-8">
          Connect authorized third-party services for this business. Sign in first.
        </p>
        <button
          onClick={() => openAuthModal("signin")}
          className="px-6 py-2.5 rounded-xl bg-accent text-bg font-semibold text-sm"
        >
          Sign in to Workspace
        </button>
      </div>
    );
  }

  const items = data?.integrations || [];

  return (
    <div className="space-y-6">
      <div>
        <h1 className="text-xl font-bold text-ink flex items-center gap-2">
          <span>🔌</span>
          <span>Integrations</span>
        </h1>
        <p className="text-xs text-muted mt-0.5">
          Authorized connections for {currentWorkspace?.name || "this business"}. A website URL is
          research (Business Intel) — never a connection credential.
        </p>
      </div>

      {msg && <div className="text-xs text-muted">{msg}</div>}
      {error && <div className="text-xs text-bad">Failed to load integrations.</div>}

      {isLoading ? (
        <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-4">
          {[1, 2, 3].map((i) => (
            <div key={i} className="h-44 rounded-2xl bg-white/[0.02] border border-white/5 animate-pulse" />
          ))}
        </div>
      ) : (
        <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-4">
          {items.map((t) => {
            const connected = t.status === "connected";
            const needsConfig = t.status === "configuration_required";
            return (
              <div
                key={t.provider}
                className="p-5 rounded-2xl bg-[#0e1217] border border-white/[0.08] flex flex-col justify-between"
              >
                <div>
                  <div className="flex items-start justify-between gap-3 mb-3">
                    <div className="flex items-center gap-3">
                      <div className="w-10 h-10 rounded-xl bg-white/[0.04] border border-white/10 flex items-center justify-center text-lg">
                        {ICONS[t.provider] || "🔌"}
                      </div>
                      <div>
                        <h2 className="text-sm font-semibold text-ink">{t.name}</h2>
                        <span className="text-[10px] px-2 py-0.2 rounded-full bg-white/5 text-muted border border-white/5">
                          {t.auth_type}
                        </span>
                      </div>
                    </div>
                    <span
                      className={`px-2 py-0.5 rounded-full text-[10px] font-bold uppercase ${
                        connected
                          ? "bg-ok/10 text-ok border border-ok/20"
                          : needsConfig
                            ? "bg-warn/10 text-warn border border-warn/20"
                            : "bg-white/5 text-muted border border-white/10"
                      }`}
                    >
                      {connected ? "Connected" : needsConfig ? "Configuration required" : t.status}
                    </span>
                  </div>
                  <p className="text-xs text-muted mb-1">{t.description}</p>
                  {t.account && <p className="text-[11px] text-muted">Connected business: {t.account}</p>}
                  {t.detail && !connected && <p className="text-[11px] text-warn mt-1">{t.detail}</p>}
                  {t.note && <p className="text-[11px] text-muted mt-1">{t.note}</p>}
                  <div className="flex flex-wrap gap-1 mt-2">
                    {t.actions.map((op) => (
                      <span
                        key={op}
                        className="px-2 py-0.5 rounded-md bg-white/[0.03] border border-white/[0.06] text-[10px] font-mono text-accent"
                      >
                        {op}
                      </span>
                    ))}
                  </div>
                </div>
                <div className="flex gap-2 mt-4">
                  {connected ? (
                    <button
                      onClick={() => handleDisconnect(t.provider)}
                      disabled={busy === t.provider}
                      className="px-3 py-1.5 rounded-lg bg-white/5 border border-white/10 text-xs hover:bg-white/10"
                    >
                      Disconnect
                    </button>
                  ) : (
                    <button
                      onClick={() => handleConnect(t.provider)}
                      disabled={busy === t.provider}
                      className="px-3 py-1.5 rounded-lg bg-accent text-bg text-xs font-semibold disabled:opacity-50"
                    >
                      {busy === t.provider ? "Checking…" : "Connect"}
                    </button>
                  )}
                </div>
              </div>
            );
          })}
        </div>
      )}
    </div>
  );
}
