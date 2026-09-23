"use client";

import { Suspense, useEffect, useState } from "react";
import Link from "next/link";
import { useSearchParams } from "next/navigation";
import { api } from "@/lib/api";

function IdeaBody() {
  const params = useSearchParams();
  const [idea, setIdea] = useState("");
  const [parsed, setParsed] = useState<Record<string, unknown> | null>(null);
  const [validation, setValidation] = useState<{
    findings: string[]; sources: string[]; assumptions: string[];
    risks: string[]; opportunities: string[]; open_questions: string[];
    research_status: string;
  } | null>(null);
  const [busy, setBusy] = useState(false);
  const [msg, setMsg] = useState<string | null>(null);

  useEffect(() => {
    const q = params.get("idea");
    if (q) setIdea(q);
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  async function handleUnderstand() {
    setBusy(true);
    setMsg(null);
    try {
      setParsed(await api.startupIdea(idea));
    } catch (e) {
      setMsg((e as Error).message);
    } finally {
      setBusy(false);
    }
  }

  async function handleValidate() {
    setBusy(true);
    try {
      setValidation(await api.startupValidate(idea));
    } catch (e) {
      setMsg((e as Error).message);
    } finally {
      setBusy(false);
    }
  }

  return (
    <div className="space-y-6">
      <div>
        <h1 className="text-2xl font-bold text-ink">💡 Startup Idea</h1>
        <p className="text-xs text-muted mt-1">What do you want to build? Everything is labeled input until researched.</p>
      </div>

      <div className="p-5 rounded-2xl bg-[#0e1217] border border-white/[0.08] space-y-3">
        <textarea
          value={idea}
          onChange={(e) => setIdea(e.target.value)}
          placeholder="e.g. food delivery startup starting in Nagpur"
          className="w-full h-28 bg-black/40 border border-white/10 rounded-xl p-3 text-sm text-ink"
        />
        <div className="flex gap-2">
          <button onClick={handleUnderstand} disabled={busy || !idea.trim()} className="px-4 py-2 rounded-xl bg-accent text-bg text-xs font-semibold disabled:opacity-50">
            Understand idea
          </button>
          <button onClick={handleValidate} disabled={busy || !idea.trim()} className="px-4 py-2 rounded-xl bg-white/5 border border-white/10 text-xs">
            Validate (research)
          </button>
        </div>
        {msg && <div className="text-xs text-bad">{msg}</div>}
      </div>

      {parsed && (
        <div className="p-5 rounded-2xl bg-[#0e1217] border border-white/[0.08] text-xs space-y-1">
          <div className="font-semibold text-ink">Structured understanding <span className="font-mono text-[10px] text-muted">[USER_INPUT]</span></div>
          {Object.entries(parsed).filter(([k]) => k !== "idea").map(([k, v]) => (
            <div key={k} className="text-muted"><span className="text-ink">{k}:</span> {Array.isArray(v) ? v.join("; ") : String(v)}</div>
          ))}
        </div>
      )}

      {validation && (
        <div className="p-5 rounded-2xl bg-[#0e1217] border border-white/[0.08] text-xs space-y-2">
          <div className="font-semibold text-ink">
            Validation <span className="font-mono text-[10px] text-muted">[{validation.research_status === "researched" ? "RESEARCHED" : "ASSUMPTIONS ONLY"}]</span>
          </div>
          {validation.findings.length > 0 && <div className="text-muted">Found: {validation.findings.join(" · ")}</div>}
          <div className="text-muted">Risks: {validation.risks.join(" · ")}</div>
          <div className="text-muted">Open: {validation.open_questions.join(" · ")}</div>
          <Link href="/startup/blueprint" className="inline-block px-4 py-2 rounded-xl bg-accent text-bg text-xs font-semibold">
            Continue to Blueprint →
          </Link>
        </div>
      )}
    </div>
  );
}

export default function StartupIdea() {
  return (
    <Suspense>
      <IdeaBody />
    </Suspense>
  );
}
