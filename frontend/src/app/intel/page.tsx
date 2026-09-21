"use client";

import { useState } from "react";
import { api } from "@/lib/api";

export default function IntelPage() {
  const [url, setUrl] = useState("https://example.com");
  const [busy, setBusy] = useState(false);
  const [result, setResult] = useState<Record<string, unknown> | null>(null);
  const [err, setErr] = useState<string | null>(null);

  async function handleAnalyze() {
    setBusy(true);
    setErr(null);
    setResult(null);
    try {
      const r = await api.analyzeWebsite(url);
      setResult(r as unknown as Record<string, unknown>);
    } catch (e) {
      setErr((e as Error).message);
    } finally {
      setBusy(false);
    }
  }

  const profile = (result?.profile as Record<string, unknown>) || null;

  return (
    <div className="space-y-6">
      <div>
        <h1 className="text-2xl font-bold text-ink">Business Intel</h1>
        <p className="text-xs text-muted mt-1">Paste website URL → fetch → extract services, target customers, CTAs → save to Knowledge Vault.</p>
      </div>

      <div className="p-5 rounded-2xl bg-[#0e1217] border border-white/[0.08] space-y-3">
        <div className="text-xs font-semibold text-ink">🌐 Website URL Analysis</div>
        <div className="flex gap-2">
          <input
            value={url}
            onChange={(e) => setUrl(e.target.value)}
            className="flex-1 bg-black/40 border border-white/10 rounded-xl px-3 py-2 text-sm text-ink"
            placeholder="https://example.com"
          />
          <button
            onClick={handleAnalyze}
            disabled={busy || !url.trim()}
            className="px-4 py-2 rounded-xl bg-accent text-bg text-xs font-semibold disabled:opacity-50"
          >
            {busy ? "Analyzing…" : "Analyze"}
          </button>
        </div>
        {err && <div className="text-xs text-bad">{err}</div>}
      </div>

      {profile && (
        <div className="p-5 rounded-2xl bg-[#0e1217] border border-white/[0.08] space-y-2 text-xs">
          <div className="font-semibold text-ink text-sm">{String(profile.company_name || "Business Profile")}</div>
          <div className="text-muted">{String(profile.description || "").slice(0, 500)}</div>
          <div className="text-muted">Pages crawled: {String(result?.pages_crawled ?? "")}</div>
          {Array.isArray(profile.services) && profile.services.length > 0 && (
            <div>
              <div className="font-semibold text-ink mt-2">Services</div>
              <ul className="list-disc ml-5 text-muted">
                {(profile.services as string[]).slice(0, 10).map((s, i) => (
                  <li key={i}>{s}</li>
                ))}
              </ul>
            </div>
          )}
          {Array.isArray(profile.ctas) && (profile.ctas as string[]).length > 0 && (
            <div className="text-muted">CTAs: {(profile.ctas as string[]).join(", ")}</div>
          )}
        </div>
      )}
    </div>
  );
}
