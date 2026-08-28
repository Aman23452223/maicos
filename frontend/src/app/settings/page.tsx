"use client";

import { useEffect, useState } from "react";
import { api, getToken } from "@/lib/api";

type SettingsOut = {
  llm_provider: string;
  llm_default_model: string;
  openrouter_configured: boolean;
  openai_configured: boolean;
  anthropic_configured: boolean;
};

async function apiRaw<T>(path: string, init: RequestInit = {}): Promise<T> {
  const token = getToken();
  const r = await fetch(`/api${path}`, {
    ...init,
    headers: {
      "Content-Type": "application/json",
      ...(token ? { Authorization: `Bearer ${token}` } : {}),
      ...(init.headers || {}),
    },
  });
  if (!r.ok) throw new Error(`${r.status}: ${await r.text()}`);
  if (r.status === 204) return undefined as T;
  return (await r.json()) as T;
}

export default function SettingsPage() {
  const [s, setS] = useState<SettingsOut | null>(null);
  const [provider, setProvider] = useState("openrouter");
  const [model, setModel] = useState("minimax/minimax-m3:free");
  const [openrouterKey, setOpenrouterKey] = useState("");
  const [msg, setMsg] = useState<string | null>(null);

  async function refresh() {
    try {
      const out = await api.getSettings();
      setS(out);
      setProvider(out.llm_provider);
      setModel(out.llm_default_model);
    } catch (e) {
      setMsg((e as Error).message);
    }
  }

  useEffect(() => {
    refresh();
  }, []);

  async function save() {
    setMsg(null);
    try {
      await api.updateSettings({
        llm_provider: provider,
        llm_default_model: model,
        openrouter_api_key: openrouterKey || undefined,
      });
      setOpenrouterKey("");
      await refresh();
      setMsg("Saved.");
    } catch (e) {
      setMsg((e as Error).message);
    }
  }

  async function test() {
    setMsg(null);
    try {
      const r = await apiRaw<{ ok: boolean; model: string; sample: string }>(
        "/v1/settings/test",
        { method: "POST" },
      );
      setMsg(`OK (${r.model}): ${r.sample}`);
    } catch (e) {
      setMsg((e as Error).message);
    }
  }

  return (
    <div className="card p-4 max-w-2xl">
      <div className="font-semibold mb-2">LLM settings</div>
      <div className="text-sm text-muted mb-4">
        Keys are stored in the running process only - never written to disk or
        logs. Use the Test button to confirm the configuration works.
      </div>
      <label className="text-xs text-muted">Provider</label>
      <select
        className="input mb-2"
        value={provider}
        onChange={(e) => setProvider(e.target.value)}
      >
        <option value="openrouter">OpenRouter (free models)</option>
        <option value="openai">OpenAI</option>
        <option value="anthropic">Anthropic</option>
      </select>

      <label className="text-xs text-muted">Default model</label>
      <input
        className="input mb-2"
        value={model}
        onChange={(e) => setModel(e.target.value)}
      />

      <label className="text-xs text-muted">OpenRouter API key</label>
      <input
        className="input mb-2"
        type="password"
        placeholder={
          s?.openrouter_configured ? "(configured)" : "sk-or-v1-..."
        }
        value={openrouterKey}
        onChange={(e) => setOpenrouterKey(e.target.value)}
      />

      <div className="flex gap-2 mt-2">
        <button className="btn" onClick={save}>
          Save
        </button>
        <button className="btn-ghost" onClick={test}>
          Test
        </button>
      </div>
      {msg && <div className="text-sm text-muted mt-3">{msg}</div>}

      <div className="mt-6 text-xs text-muted">
        Configured: OR={String(s?.openrouter_configured ?? false)} ·
        OAI={String(s?.openai_configured ?? false)} ·
        ANT={String(s?.anthropic_configured ?? false)}
      </div>
    </div>
  );
}
