"use client";

import { useEffect, useState } from "react";
import { api } from "@/lib/api";

type AnalysisType = "my_business" | "competitor" | "prospect";

const STEPS = [
  "Fetching website",
  "Reading available pages/content",
  "Extracting business information",
  "Structuring information",
  "Saving to Knowledge Vault",
];

const TYPE_HELP: Record<AnalysisType, string> = {
  my_business: "Saved to your business profile + Knowledge Vault.",
  competitor: "Stored separately as competitor intelligence. Never overwrites your profile.",
  prospect: "Stored as prospect research. Can convert to a CRM lead.",
};

function Card({ title, children }: { title: string; children: React.ReactNode }) {
  return (
    <div className="p-4 rounded-xl bg-black/40 border border-white/5">
      <div className="text-xs font-semibold text-ink mb-1.5">{title}</div>
      <div className="text-xs text-muted space-y-1">{children}</div>
    </div>
  );
}

export default function IntelPage() {
  const [url, setUrl] = useState("https://example.com");
  const [atype, setAtype] = useState<AnalysisType>("my_business");
  const [busy, setBusy] = useState(false);
  const [step, setStep] = useState(0);
  const [result, setResult] = useState<Record<string, unknown> | null>(null);
  const [err, setErr] = useState<string | null>(null);
  const [history, setHistory] = useState<
    { id: string; type: string; url: string; company_name: string; version: number; last_analyzed_at: string | null }[]
  >([]);

  async function loadHistory() {
    try {
      setHistory(await api.listIntelAnalyses());
    } catch {
      /* ignore */
    }
  }

  useEffect(() => {
    loadHistory();
  }, []);

  async function handleAnalyze() {
    setBusy(true);
    setErr(null);
    setResult(null);
    setStep(0);
    const tick = setInterval(() => setStep((s) => Math.min(s + 1, STEPS.length - 1)), 1200);
    try {
      const r = await api.analyzeWebsite(url, atype);
      setResult(r as unknown as Record<string, unknown>);
      loadHistory();
    } catch (e) {
      setErr((e as Error).message);
    } finally {
      clearInterval(tick);
      setBusy(false);
    }
  }

  async function handleConvert(id: string) {
    try {
      const r = await api.convertProspect(id);
      setErr(null);
      setResult({ ...(result || {}), converted: r });
    } catch (e) {
      setErr((e as Error).message);
    }
  }

  const profile = (result?.profile as Record<string, unknown>) || null;
  const str = (v: unknown) => String(v || "");
  const list = (v: unknown): string[] => (Array.isArray(v) ? (v as string[]) : []);

  return (
    <div className="space-y-6">
      <div>
        <h1 className="text-2xl font-bold text-ink">Business Intel</h1>
        <p className="text-xs text-muted mt-1">
          Public research only — analyzing a URL never connects to or controls that platform. Authorized
          connections live in Integrations.
        </p>
      </div>

      <div className="p-5 rounded-2xl bg-[#0e1217] border border-white/[0.08] space-y-3">
        <div className="text-xs font-semibold text-ink">🌐 Website URL Analysis</div>
        <div className="flex gap-2 text-xs" role="tablist" aria-label="Analysis Type">
          {(["my_business", "competitor", "prospect"] as AnalysisType[]).map((t) => (
            <button
              key={t}
              role="tab"
              aria-selected={atype === t}
              onClick={() => setAtype(t)}
              className={`px-3 py-1.5 rounded-lg border font-medium ${
                atype === t
                  ? "bg-accent/15 text-ink border-accent/40"
                  : "bg-white/[0.03] text-muted border-white/10 hover:text-ink"
              }`}
            >
              {t === "my_business" ? "My Business" : t === "competitor" ? "Competitor" : "Prospect"}
            </button>
          ))}
        </div>
        <div className="text-[11px] text-muted">{TYPE_HELP[atype]}</div>
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
        {busy && (
          <ol className="text-[11px] text-muted space-y-1">
            {STEPS.map((s, i) => (
              <li key={s} className={i <= step ? "text-ink" : ""}>
                {i < step ? "✓ " : i === step ? "◌ " : "○ "}
                {s}
              </li>
            ))}
          </ol>
        )}
        {err && <div className="text-xs text-bad">{err}</div>}
      </div>

      {profile && (
        <div className="space-y-3">
          <div className="p-4 rounded-xl bg-ok/10 border border-ok/20 text-xs text-ok">
            ✓ Saved to Knowledge Vault
            {result?.updated ? ` (updated to v${String(result.version)})` : ` (v${String(result?.version || 1)})`}
            {" · "}Type: {String(result?.analysis_type)}
          </div>
          <div className="grid grid-cols-1 md:grid-cols-2 gap-3">
            <Card title="Business Overview">
              <div className="font-semibold text-ink">{str(profile.company_name)}</div>
              <div>{str(profile.description).slice(0, 400)}</div>
              <div>Industry: {list(profile.industries_served).join(", ") || "—"}</div>
              <div>Pages crawled: {String(result?.pages_crawled ?? "")}</div>
            </Card>
            <Card title="Target Customers">
              <div>{str(profile.target_customer) || "—"}</div>
            </Card>
            <Card title="Services">
              {list(profile.services).length > 0
                ? list(profile.services).slice(0, 8).map((s, i) => <div key={i}>• {s}</div>)
                : "—"}
            </Card>
            <Card title="Products / Menu">
              {[...list(profile.menu), ...list(profile.products)].length > 0
                ? [...list(profile.menu), ...list(profile.products)].slice(0, 8).map((s, i) => (
                    <div key={i}>• {s}</div>
                  ))
                : "—"}
            </Card>
            <Card title="Offers">
              {list(profile.offers).length > 0
                ? list(profile.offers).slice(0, 6).map((s, i) => <div key={i}>• {s}</div>)
                : "—"}
            </Card>
            <Card title="Contact Information">
              <div>Emails: {list(profile.emails).join(", ") || "—"}</div>
              <div>Phones: {list(profile.phones).join(", ") || "—"}</div>
              <div>Social: {list(profile.social_links).slice(0, 4).join(", ") || "—"}</div>
            </Card>
            <Card title="Location">
              <div>{str(profile.geography) || "—"}</div>
            </Card>
            <Card title="Opening Hours">
              <div>{str(profile.opening_hours) || "—"}</div>
            </Card>
            <Card title="CTAs">
              <div>{list(profile.ctas).join(" · ") || "—"}</div>
            </Card>
            <Card title="FAQs">
              {Array.isArray(profile.faqs) && (profile.faqs as { question: string }[]).length > 0 ? (
                (profile.faqs as { question: string }[]).slice(0, 5).map((f, i) => <div key={i}>• {f.question}</div>)
              ) : (
                <span>—</span>
              )}
            </Card>
          </div>
          {String(result?.analysis_type) === "prospect" && String(result?.analysis_id || "") && (
            <button
              onClick={() => handleConvert(String(result?.analysis_id || ""))}
              className="px-4 py-2 rounded-xl bg-ok text-bg text-xs font-semibold"
            >
              Convert to CRM Lead
            </button>
          )}
        </div>
      )}

      {history.length > 0 && (
        <div className="p-5 rounded-2xl bg-[#0e1217] border border-white/[0.08]">
          <div className="text-xs font-semibold text-ink mb-2">Past analyses (this workspace only)</div>
          <div className="text-[11px] text-muted space-y-1">
            {history.map((h) => (
              <div key={h.id} className="flex justify-between gap-2">
                <span className="truncate">
                  [{h.type}] {h.company_name || h.url}
                </span>
                <span className="font-mono">v{h.version}</span>
              </div>
            ))}
          </div>
        </div>
      )}
    </div>
  );
}
