"use client";

import { useState } from "react";
import Link from "next/link";
import { api } from "@/lib/api";

export default function ExplorePage() {
  const [idea, setIdea] = useState("");
  const [result, setResult] = useState<{
    findings: string[]; sources: string[]; assumptions: string[];
    risks: string[]; opportunities: string[]; open_questions: string[];
    research_status: string;
  } | null>(null);
  const [busy, setBusy] = useState(false);

  async function handleExplore() {
    setBusy(true);
    try {
      setResult(await api.startupValidate(idea));
    } catch {
      setResult(null);
    } finally {
      setBusy(false);
    }
  }

  return (
    <div className="space-y-6">
      <div>
        <h1 className="text-2xl font-bold text-ink">💡 Explore an Idea</h1>
        <p className="text-xs text-muted mt-1">Research only — nothing executes, no infrastructure touched.</p>
      </div>

      <div className="p-5 rounded-2xl bg-[#0e1217] border border-white/[0.08] space-y-3">
        <textarea
          value={idea}
          onChange={(e) => setIdea(e.target.value)}
          placeholder="e.g. AI marketplace connecting local clothing stores with customers"
          className="w-full h-24 bg-black/40 border border-white/10 rounded-xl p-3 text-sm text-ink"
        />
        <button onClick={handleExplore} disabled={busy || !idea.trim()} className="px-4 py-2 rounded-xl bg-accent text-bg text-xs font-semibold disabled:opacity-50">
          {busy ? "Researching…" : "Validate idea"}
        </button>
      </div>

      {result && (
        <div className="p-5 rounded-2xl bg-[#0e1217] border border-white/[0.08] text-xs space-y-2">
          <div className="font-semibold text-ink">
            Verdict inputs <span className="font-mono text-[10px] text-muted">[{result.research_status === "researched" ? "RESEARCHED" : "ASSUMPTIONS ONLY"}]</span>
          </div>
          {result.findings.length > 0 && <div className="text-muted">Market signals: {result.findings.join(" · ")}</div>}
          <div className="text-muted">Risks: {result.risks.join(" · ")}</div>
          <div className="text-muted">Opportunities: {result.opportunities.join(" · ")}</div>
          <div className="text-muted">Open questions: {result.open_questions.join(" · ")}</div>
          <Link
            href={`/startup/idea?idea=${encodeURIComponent(idea)}`}
            className="inline-block px-4 py-2 rounded-xl bg-ok text-bg text-xs font-semibold"
          >
            Build This Startup →
          </Link>
        </div>
      )}
    </div>
  );
}
