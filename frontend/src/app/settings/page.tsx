"use client";

import { useEffect, useState, useCallback } from "react";
import { api, getToken } from "@/lib/api";
import { useAuth } from "@/contexts/AuthContext";

type SettingsOut = {
  llm_provider: string;
  llm_default_model: string;
  openrouter_configured: boolean;
  openai_configured: boolean;
  anthropic_configured: boolean;
};

async function testSettingsRaw(): Promise<{ ok: boolean; model: string; sample: string }> {
  const token = getToken();
  const r = await fetch("/api/v1/settings/test", {
    method: "POST",
    headers: {
      "Content-Type": "application/json",
      ...(token ? { Authorization: `Bearer ${token}` } : {}),
    },
  });
  if (!r.ok) throw new Error(`${r.status}: ${await r.text()}`);
  return (await r.json()) as { ok: boolean; model: string; sample: string };
}

export default function SettingsPage() {
  const { user, openAuthModal } = useAuth();
  const [s, setS] = useState<SettingsOut | null>(null);
  const [provider, setProvider] = useState("openrouter");
  const [model, setModel] = useState("minimax/minimax-m3:free");
  const [openrouterKey, setOpenrouterKey] = useState("");
  const [saving, setSaving] = useState(false);
  const [testing, setTesting] = useState(false);
  const [msg, setMsg] = useState<string | null>(null);
  const [err, setErr] = useState<string | null>(null);

  const refresh = useCallback(async () => {
    if (!user) return;
    try {
      const out = await api.getSettings();
      setS(out);
      setProvider(out.llm_provider);
      setModel(out.llm_default_model);
    } catch (e) {
      setErr((e as Error).message);
    }
  }, [user]);

  useEffect(() => {
    if (user) refresh();
  }, [user, refresh]);

  async function handleSave(e: React.FormEvent) {
    e.preventDefault();
    setSaving(true);
    setMsg(null);
    setErr(null);
    try {
      await api.updateSettings({
        llm_provider: provider,
        llm_default_model: model,
        openrouter_api_key: openrouterKey || undefined,
      });
      setOpenrouterKey("");
      await refresh();
      setMsg("Settings saved successfully.");
    } catch (e) {
      setErr((e as Error).message);
    } finally {
      setSaving(false);
    }
  }

  async function handleTest() {
    setTesting(true);
    setMsg(null);
    setErr(null);
    try {
      const r = await testSettingsRaw();
      setMsg(`✓ LLM Connection OK! Model: ${r.model}. Output: "${r.sample}"`);
    } catch (e) {
      setErr((e as Error).message);
    } finally {
      setTesting(false);
    }
  }

  if (!user) {
    return (
      <div className="max-w-2xl mx-auto py-12 px-4 text-center">
        <div className="w-16 h-16 mx-auto mb-6 rounded-2xl bg-gradient-to-tr from-accent/20 to-purple-500/20 border border-accent/30 flex items-center justify-center text-2xl shadow-[0_0_30px_rgba(91,141,239,0.2)]">
          ⚙️
        </div>
        <h1 className="text-2xl font-bold tracking-tight text-ink mb-2">
          System & LLM Settings
        </h1>
        <p className="text-sm text-muted max-w-md mx-auto mb-8">
          Configure model routing (OpenRouter, OpenAI, Anthropic) and workspace API keys. Sign in to update configuration.
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
    <div className="space-y-6 max-w-3xl">
      {/* Header */}
      <div>
        <h1 className="text-xl font-bold tracking-tight text-ink flex items-center gap-2">
          <span>⚙️</span>
          <span>System & LLM Engine Settings</span>
        </h1>
        <p className="text-xs text-muted mt-0.5">
          Configure foundation model providers, default reasoning models, and encrypted API credentials.
        </p>
      </div>

      {/* Provider Status Indicators */}
      <div className="grid grid-cols-1 sm:grid-cols-3 gap-3">
        <div className="p-3.5 rounded-xl bg-[#0e1217] border border-white/[0.08] flex items-center justify-between">
          <span className="text-xs text-muted">OpenRouter</span>
          <span
            className={`px-2 py-0.5 rounded-full text-[10px] font-mono ${
              s?.openrouter_configured ? "bg-ok/10 text-ok" : "bg-white/5 text-muted"
            }`}
          >
            {s?.openrouter_configured ? "Configured" : "Not Set"}
          </span>
        </div>
        <div className="p-3.5 rounded-xl bg-[#0e1217] border border-white/[0.08] flex items-center justify-between">
          <span className="text-xs text-muted">OpenAI</span>
          <span
            className={`px-2 py-0.5 rounded-full text-[10px] font-mono ${
              s?.openai_configured ? "bg-ok/10 text-ok" : "bg-white/5 text-muted"
            }`}
          >
            {s?.openai_configured ? "Configured" : "Not Set"}
          </span>
        </div>
        <div className="p-3.5 rounded-xl bg-[#0e1217] border border-white/[0.08] flex items-center justify-between">
          <span className="text-xs text-muted">Anthropic</span>
          <span
            className={`px-2 py-0.5 rounded-full text-[10px] font-mono ${
              s?.anthropic_configured ? "bg-ok/10 text-ok" : "bg-white/5 text-muted"
            }`}
          >
            {s?.anthropic_configured ? "Configured" : "Not Set"}
          </span>
        </div>
      </div>

      {/* Main Settings Form */}
      <div className="p-6 rounded-2xl bg-[#0e1217] border border-white/[0.08] shadow-lg">
        <form onSubmit={handleSave} className="space-y-4">
          <div>
            <label className="block text-xs font-medium text-muted mb-1">
              Active LLM Provider
            </label>
            <select
              value={provider}
              onChange={(e) => setProvider(e.target.value)}
              className="w-full bg-black/40 border border-white/10 rounded-lg px-3 py-2 text-xs text-ink focus:outline-none focus:border-accent font-sans"
            >
              <option value="openrouter">OpenRouter (Free & Premium Models)</option>
              <option value="openai">OpenAI (Direct API)</option>
              <option value="anthropic">Anthropic Claude (Direct API)</option>
            </select>
          </div>

          <div>
            <label className="block text-xs font-medium text-muted mb-1">
              Default Reasoning Model
            </label>
            <input
              type="text"
              value={model}
              onChange={(e) => setModel(e.target.value)}
              placeholder="minimax/minimax-m3:free"
              className="w-full bg-black/40 border border-white/10 rounded-lg px-3 py-2 text-xs text-ink focus:outline-none focus:border-accent font-mono"
              required
            />
            <span className="text-[11px] text-muted/60 mt-1 block">
              Examples: <code>minimax/minimax-m3:free</code>, <code>meta-llama/llama-3.3-70b-instruct:free</code>, <code>openai/gpt-4o-mini</code>
            </span>
          </div>

          <div>
            <label className="block text-xs font-medium text-muted mb-1">
              OpenRouter API Key
            </label>
            <input
              type="password"
              value={openrouterKey}
              onChange={(e) => setOpenrouterKey(e.target.value)}
              placeholder={s?.openrouter_configured ? "•••••••••••••••• (configured)" : "sk-or-v1-..."}
              className="w-full bg-black/40 border border-white/10 rounded-lg px-3 py-2 text-xs text-ink focus:outline-none focus:border-accent font-mono"
            />
            <span className="text-[11px] text-muted/60 mt-1 block">
              Leave blank to keep existing configured key. Keys are held in memory only.
            </span>
          </div>

          {msg && (
            <div className="p-3 rounded-lg bg-ok/10 border border-ok/30 text-ok text-xs">
              {msg}
            </div>
          )}

          {err && (
            <div className="p-3 rounded-lg bg-bad/10 border border-bad/30 text-bad text-xs">
              {err}
            </div>
          )}

          <div className="flex items-center gap-3 pt-2">
            <button
              type="submit"
              disabled={saving}
              className="px-5 py-2 rounded-xl bg-accent hover:bg-accent/90 text-bg font-semibold text-xs transition-all shadow-[0_0_15px_rgba(91,141,239,0.3)] disabled:opacity-50"
            >
              {saving ? "Saving…" : "Save Configuration"}
            </button>

            <button
              type="button"
              onClick={handleTest}
              disabled={testing}
              className="px-4 py-2 rounded-xl bg-white/5 hover:bg-white/10 text-ink border border-white/10 text-xs font-medium transition-all disabled:opacity-50"
            >
              {testing ? "Testing Connectivity…" : "⚡ Test Latency & Ping"}
            </button>
          </div>
        </form>
      </div>
    </div>
  );
}
