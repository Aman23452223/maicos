"use client";

import { useState } from "react";
import { api } from "@/lib/api";
import { useAuth } from "@/contexts/AuthContext";
import type { Workflow, WorkflowTask } from "@/lib/types";

const QUICK_PROMPTS = [
  "Onboard the new client ABC with full billing setup and welcome checklist.",
  "Run a complete financial audit on Q3 Stripe revenues and flag any billing discrepancies.",
  "Scan knowledge vault documents and summarize the updated customer refund policy.",
  "Sync CRM records with outreach campaign results and draft weekly executive digest.",
];

export default function CommandPage() {
  const { user, openAuthModal } = useAuth();
  const [objective, setObjective] = useState(
    "Onboard the new client ABC with full billing setup and welcome checklist."
  );
  const [busy, setBusy] = useState(false);
  const [err, setErr] = useState<string | null>(null);
  const [wf, setWf] = useState<Workflow | null>(null);
  const [tasks, setTasks] = useState<WorkflowTask[]>([]);
  const [scheduleAt, setScheduleAt] = useState("");
  const [scheduledMsg, setScheduledMsg] = useState<string | null>(null);

  async function handleSubmit(e?: React.FormEvent) {
    if (e) e.preventDefault();
    if (!objective.trim()) return;

    if (!user) {
      openAuthModal("signin");
      return;
    }

    setBusy(true);
    setErr(null);
    try {
      const w = await api.submitCommand(objective);
      setWf(w);
      const ts = await api.listTasks(w.id);
      setTasks(ts);
    } catch (e) {
      setErr((e as Error).message);
    } finally {
      setBusy(false);
    }
  }

  async function handleResume() {
    if (!wf) return;
    setBusy(true);
    try {
      const w = await api.resume(wf.id);
      setWf(w);
      const ts = await api.listTasks(w.id);
      setTasks(ts);
    } catch (e) {
      setErr((e as Error).message);
    } finally {
      setBusy(false);
    }
  }

  async function handleSchedule() {
    if (!scheduleAt) return;
    if (!user) {
      openAuthModal("signin");
      return;
    }

    setScheduledMsg(null);
    try {
      const iso = new Date(scheduleAt).toISOString();
      const r = await api.scheduleWorkflow(objective, iso);
      setScheduledMsg(`Scheduled job ${r.job_id.slice(0, 8)} for ${new Date(r.run_at).toLocaleString()}`);
    } catch (e) {
      setScheduledMsg((e as Error).message);
    }
  }

  return (
    <div className="space-y-6">
      {/* Title */}
      <div>
        <div className="inline-flex items-center gap-2 px-2.5 py-1 rounded-full bg-accent/10 border border-accent/20 text-accent text-xs font-semibold uppercase tracking-wider mb-2">
          <span className="w-2 h-2 rounded-full bg-accent animate-pulse" />
          Autonomous Dispatch
        </div>
        <h1 className="text-2xl font-bold tracking-tight text-ink">
          AI Command Center
        </h1>
        <p className="text-xs text-muted mt-1 max-w-xl">
          State your business objective in plain English. The Executive Agent will deconstruct it, assign specialized agents, and coordinate execution.
        </p>
      </div>

      {/* Main Command Console & Status Panel */}
      <div className="grid grid-cols-1 lg:grid-cols-3 gap-6">
        {/* Left 2 Cols: Prompt Terminal */}
        <div className="lg:col-span-2 space-y-4">
          <div className="p-5 rounded-2xl bg-[#0e1217] border border-white/[0.08] shadow-lg relative overflow-hidden">
            <div className="flex items-center justify-between mb-3 text-xs">
              <span className="font-semibold text-ink flex items-center gap-2">
                <span>⚡</span>
                <span>Objective Formulation</span>
              </span>
              <span className="text-[11px] text-muted font-mono">
                Model: Minimax / GPT-4o
              </span>
            </div>

            <textarea
              className="w-full h-36 bg-black/40 border border-white/10 rounded-xl p-3.5 text-sm text-ink placeholder:text-muted/50 focus:outline-none focus:border-accent transition-colors font-sans resize-none"
              placeholder="Describe what outcome you want your AI workforce to deliver…"
              value={objective}
              onChange={(e) => setObjective(e.target.value)}
            />

            {/* Quick Prompts */}
            <div className="mt-3">
              <span className="text-[11px] text-muted font-mono block mb-1.5">
                Preset Objectives:
              </span>
              <div className="flex flex-wrap gap-1.5">
                {QUICK_PROMPTS.map((prompt, i) => (
                  <button
                    key={i}
                    onClick={() => setObjective(prompt)}
                    className="text-[11px] text-muted hover:text-ink px-2.5 py-1 rounded-md bg-white/[0.03] hover:bg-white/[0.08] border border-white/5 transition-all truncate max-w-xs text-left"
                  >
                    "{prompt}"
                  </button>
                ))}
              </div>
            </div>

            {/* Error Message */}
            {err && (
              <div className="mt-3 p-3 rounded-lg bg-bad/10 border border-bad/30 text-bad text-xs">
                {err}
              </div>
            )}

            {/* Actions */}
            <div className="flex items-center justify-between gap-3 mt-4 pt-4 border-t border-white/5">
              <div className="flex items-center gap-2">
                <button
                  onClick={() => handleSubmit()}
                  disabled={busy || !objective.trim()}
                  className="px-5 py-2.5 rounded-xl bg-accent hover:bg-accent/90 text-bg font-semibold text-xs transition-all shadow-[0_0_15px_rgba(91,141,239,0.3)] disabled:opacity-50 flex items-center gap-2"
                >
                  {busy ? (
                    <>
                      <span className="w-3.5 h-3.5 border-2 border-bg border-t-transparent rounded-full animate-spin" />
                      <span>Synthesizing Plan…</span>
                    </>
                  ) : (
                    <>
                      <span>⚡</span>
                      <span>Dispatch Workforce</span>
                    </>
                  )}
                </button>

                {wf && wf.state === "WAITING_APPROVAL" && (
                  <button
                    onClick={handleResume}
                    disabled={busy}
                    className="px-4 py-2.5 rounded-xl bg-warn/15 hover:bg-warn/25 text-warn border border-warn/30 font-semibold text-xs transition-all"
                  >
                    Resume After Approvals
                  </button>
                )}
              </div>

              {!user && (
                <span className="text-[11px] text-muted">
                  Requires <button onClick={() => openAuthModal("signin")} className="text-accent underline font-semibold">Sign In</button>
                </span>
              )}
            </div>
          </div>

          {/* Scheduler Card */}
          <div className="p-4 rounded-xl bg-white/[0.02] border border-white/[0.06] flex flex-col sm:flex-row sm:items-center justify-between gap-3">
            <div>
              <div className="text-xs font-semibold text-ink flex items-center gap-1.5">
                <span>⏱️</span>
                <span>Schedule Workflow for Future Execution</span>
              </div>
              <p className="text-[11px] text-muted mt-0.5">
                Set a precise UTC timestamp for automated deferred execution.
              </p>
            </div>

            <div className="flex items-center gap-2">
              <input
                type="datetime-local"
                value={scheduleAt}
                onChange={(e) => setScheduleAt(e.target.value)}
                className="bg-black/40 border border-white/10 rounded-lg px-2.5 py-1.5 text-xs text-ink focus:outline-none focus:border-accent"
              />
              <button
                onClick={handleSchedule}
                disabled={!scheduleAt}
                className="px-3 py-1.5 rounded-lg bg-white/5 hover:bg-white/10 border border-white/10 text-xs text-ink transition-colors disabled:opacity-40"
              >
                Schedule
              </button>
            </div>
          </div>

          {scheduledMsg && (
            <div className="p-2.5 rounded-lg bg-ok/10 border border-ok/20 text-ok text-xs">
              ✓ {scheduledMsg}
            </div>
          )}
        </div>

        {/* Right 1 Col: Live Execution Pipeline Card */}
        <div className="p-5 rounded-2xl bg-[#0e1217] border border-white/[0.08] shadow-lg flex flex-col justify-between">
          <div>
            <div className="flex items-center justify-between mb-4">
              <h2 className="text-xs font-semibold text-ink uppercase tracking-wider font-mono">
                Execution Pipeline
              </h2>
              {wf && (
                <span
                  className={`px-2 py-0.5 rounded-full text-[10px] font-bold uppercase tracking-wider ${
                    wf.state === "COMPLETED"
                      ? "bg-ok/10 text-ok border border-ok/20"
                      : wf.state === "FAILED"
                      ? "bg-bad/10 text-bad border border-bad/20"
                      : wf.state === "WAITING_APPROVAL"
                      ? "bg-warn/10 text-warn border border-warn/20 animate-pulse"
                      : "bg-accent/10 text-accent border border-accent/20 animate-pulse"
                  }`}
                >
                  {wf.state}
                </span>
              )}
            </div>

            {!wf ? (
              <div className="text-center py-10">
                <div className="w-10 h-10 mx-auto mb-3 rounded-full bg-white/[0.04] border border-white/[0.08] flex items-center justify-center text-lg text-muted">
                  💤
                </div>
                <h3 className="text-xs font-semibold text-ink">Engine Idle</h3>
                <p className="text-[11px] text-muted mt-1 max-w-[200px] mx-auto">
                  Submit an objective on the left to initialize agent planning and task breakdown.
                </p>
              </div>
            ) : (
              <div className="space-y-3">
                <div className="p-3 rounded-xl bg-black/40 border border-white/5 space-y-1">
                  <div className="text-[10px] font-mono text-muted uppercase">Workflow ID</div>
                  <div className="text-xs font-mono text-ink truncate">{wf.id}</div>
                </div>

                <div className="p-3 rounded-xl bg-black/40 border border-white/5 space-y-1">
                  <div className="text-[10px] font-mono text-muted uppercase">Generated Plan</div>
                  <div className="text-xs text-ink font-semibold">{wf.title}</div>
                  <div className="text-[11px] text-muted line-clamp-2">{wf.objective}</div>
                </div>

                <div className="p-3 rounded-xl bg-black/40 border border-white/5">
                  <div className="flex justify-between items-center text-xs">
                    <span className="text-muted">Tasks Generated:</span>
                    <span className="font-mono text-ink font-bold">
                      {tasks.length || wf.plan?.tasks?.length || 0}
                    </span>
                  </div>
                </div>
              </div>
            )}
          </div>

          <div className="mt-6 pt-4 border-t border-white/5 text-[11px] text-muted flex items-center justify-between">
            <span>Autonomy Level: High</span>
            <span className="text-accent font-mono">11 Agents Ready</span>
          </div>
        </div>
      </div>

      {/* Task Breakdown Table */}
      {tasks.length > 0 && (
        <div className="p-5 rounded-2xl bg-[#0e1217] border border-white/[0.08] shadow-lg space-y-3">
          <div className="flex items-center justify-between">
            <h3 className="text-sm font-semibold text-ink flex items-center gap-2">
              <span>📋</span>
              <span>Delegated Task Breakdown</span>
            </h3>
            <span className="text-xs font-mono text-muted">{tasks.length} sub-tasks</span>
          </div>

          <div className="overflow-x-auto">
            <table className="w-full text-xs text-left">
              <thead className="text-muted border-b border-white/[0.08]">
                <tr>
                  <th className="py-2.5 font-medium">Assigned Agent</th>
                  <th className="font-medium">Task Specification</th>
                  <th className="font-medium">State</th>
                  <th className="font-medium">Output / Notes</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-white/5">
                {tasks.map((t) => (
                  <tr key={t.id} className="hover:bg-white/[0.02]">
                    <td className="py-2.5 font-mono text-accent font-semibold">
                      🤖 {t.agent_name}
                    </td>
                    <td className="max-w-md">
                      <div className="font-medium text-ink">{t.title}</div>
                      <div className="text-[11px] text-muted truncate">{t.description}</div>
                    </td>
                    <td>
                      <span
                        className={`px-2 py-0.5 rounded-full text-[10px] font-bold uppercase ${
                          t.state === "COMPLETED"
                            ? "bg-ok/10 text-ok border border-ok/20"
                            : t.state === "FAILED"
                            ? "bg-bad/10 text-bad border border-bad/20"
                            : t.state === "RUNNING"
                            ? "bg-accent/10 text-accent border border-accent/20 animate-pulse"
                            : "bg-white/5 text-muted"
                        }`}
                      >
                        {t.state}
                      </span>
                    </td>
                    <td className="text-muted font-mono text-[11px]">
                      {t.error ? (
                        <span className="text-bad">{t.error}</span>
                      ) : t.output && Object.keys(t.output).length > 0 ? (
                        <span className="text-ok">Completed</span>
                      ) : (
                        "—"
                      )}
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </div>
      )}
    </div>
  );
}
