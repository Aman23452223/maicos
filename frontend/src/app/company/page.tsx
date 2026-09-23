"use client";

import { useEffect, useState } from "react";
import { api } from "@/lib/api";
import { useAuth } from "@/contexts/AuthContext";

export default function CompanyPage() {
  const { user, currentWorkspace } = useAuth();
  const [objective, setObjective] = useState("");
  const [busy, setBusy] = useState(false);
  const [msg, setMsg] = useState<string | null>(null);
  const [team, setTeam] = useState<{ role: string; agent: string; capability: string; available: boolean }[]>([]);
  const [signals, setSignals] = useState<{ id: string; kind: string; severity: string; title: string; detail: string }[]>([]);
  const [usage, setUsage] = useState<{ tasks: number; tool_calls: number } | null>(null);
  const [idea, setIdea] = useState("");
  const [blueprint, setBlueprint] = useState<Record<string, { status: string; text: string }> | null>(null);

  async function load() {
    try {
      setSignals(await api.companySignals());
      setUsage(await api.companyUsage());
      const wf = await api.companyWorkforce("campaign");
      setTeam(wf.team);
    } catch {
      /* ignore */
    }
  }

  useEffect(() => {
    if (user) load();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [user]);

  async function handleRun() {
    if (!objective.trim()) return;
    setBusy(true);
    setMsg(null);
    try {
      const w = (await api.companyRun(objective, true)) as unknown as Record<string, unknown>;
      const wid = String(w.workflow_id || w.id || "");
      setMsg(
        wid
          ? `Workforce dispatched as ${wid.slice(0, 8)} — review the plan in Approvals, then approve to run.`
          : `Dispatched (state: ${String(w.state || "unknown")}) — check Approvals.`,
      );
      setObjective("");
    } catch (e) {
      setMsg((e as Error).message);
    } finally {
      setBusy(false);
    }
  }

  async function handleCheckup() {
    try {
      const r = await api.companyCheckup();
      setMsg(`Checkup: ${r.signals_created} new signal(s).`);
      setSignals(await api.companySignals());
    } catch (e) {
      setMsg((e as Error).message);
    }
  }

  async function handleBlueprint() {
    if (!idea.trim()) return;
    try {
      const r = await api.companyBlueprint(idea);
      setBlueprint(r.sections);
      setMsg("Blueprint ready — review below. Assumptions are NOT facts.");
    } catch (e) {
      setMsg((e as Error).message);
    }
  }

  return (
    <div className="space-y-6">
      <div>
        <h1 className="text-2xl font-bold text-ink">Company Command Center</h1>
        <p className="text-xs text-muted mt-1">
          {currentWorkspace ? `${currentWorkspace.name} · ` : ""}Outcome in, workforce out. You manage the
          company — MAICOS manages the work.
        </p>
      </div>
      {msg && <div className="text-xs text-muted">{msg}</div>}

      <div className="p-5 rounded-2xl bg-[#0e1217] border border-white/[0.08] space-y-3">
        <div className="text-xs font-semibold text-ink">🎯 What should your company accomplish?</div>
        <div className="flex gap-2">
          <input
            value={objective}
            onChange={(e) => setObjective(e.target.value)}
            placeholder="e.g. I need 100 qualified customers this month"
            className="flex-1 bg-black/40 border border-white/10 rounded-xl px-3 py-2 text-sm text-ink"
          />
          <button
            onClick={handleRun}
            disabled={busy || !objective.trim()}
            className="px-4 py-2 rounded-xl bg-accent text-bg text-xs font-semibold disabled:opacity-50"
          >
            {busy ? "Planning…" : "Run via Company Manager"}
          </button>
        </div>
      </div>

      <div className="grid grid-cols-1 lg:grid-cols-2 gap-3">
        <div className="p-5 rounded-2xl bg-[#0e1217] border border-white/[0.08]">
          <div className="text-xs font-semibold text-ink mb-2">🤖 Available workforce</div>
          <div className="text-xs text-muted space-y-1">
            {team.map((t) => (
              <div key={t.role} className="flex justify-between gap-2">
                <span>{t.role} <span className="font-mono text-muted/70">({t.agent})</span></span>
                <span className={t.available ? "text-ok" : "text-warn"}>
                  {t.available ? "ready" : "needs config"}
                </span>
              </div>
            ))}
          </div>
        </div>
        <div className="p-5 rounded-2xl bg-[#0e1217] border border-white/[0.08]">
          <div className="flex items-center justify-between mb-2">
            <div className="text-xs font-semibold text-ink">🚨 Open signals</div>
            <button onClick={handleCheckup} className="px-3 py-1 rounded-lg bg-white/5 border border-white/10 text-[11px]">
              Run checkup
            </button>
          </div>
          <div className="text-xs text-muted space-y-1">
            {signals.map((s) => (
              <div key={s.id}>[{s.severity}] {s.title}</div>
            ))}
            {signals.length === 0 && <span>All clear. Usage: {usage ? `${usage.tasks} tasks, ${usage.tool_calls} tool calls` : "—"}</span>}
          </div>
        </div>
      </div>

      <div className="p-5 rounded-2xl bg-[#0e1217] border border-white/[0.08] space-y-3">
        <div className="text-xs font-semibold text-ink">💡 New startup blueprint</div>
        <div className="flex gap-2">
          <input
            value={idea}
            onChange={(e) => setIdea(e.target.value)}
            placeholder="e.g. food delivery startup in Nagpur"
            className="flex-1 bg-black/40 border border-white/10 rounded-xl px-3 py-2 text-sm text-ink"
          />
          <button onClick={handleBlueprint} className="px-4 py-2 rounded-xl bg-white/5 border border-white/10 text-xs">
            Generate
          </button>
        </div>
        {blueprint && (
          <div className="text-xs text-muted space-y-1.5 max-h-72 overflow-y-auto">
            {Object.entries(blueprint).map(([k, v]) => (
              <div key={k}>
                <span className="text-ink font-medium">{k}</span>{" "}
                <span className="font-mono text-[10px]">[{v.status}]</span>
                <div>{v.text}</div>
              </div>
            ))}
          </div>
        )}
      </div>
    </div>
  );
}
