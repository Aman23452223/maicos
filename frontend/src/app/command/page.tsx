"use client";

import { useState } from "react";
import { api } from "@/lib/api";
import type { Workflow, WorkflowTask } from "@/lib/types";
import { statePillClass } from "@/lib/ui";

export default function CommandPage() {
  const [objective, setObjective] = useState("Onboard the new client ABC.");
  const [busy, setBusy] = useState(false);
  const [err, setErr] = useState<string | null>(null);
  const [wf, setWf] = useState<Workflow | null>(null);
  const [tasks, setTasks] = useState<WorkflowTask[]>([]);

  const [scheduleAt, setScheduleAt] = useState("");
  const [scheduledMsg, setScheduledMsg] = useState<string | null>(null);

  async function scheduleRun() {
    if (!scheduleAt) return;
    setScheduledMsg(null);
    try {
      const iso = new Date(scheduleAt).toISOString();
      const r = await api.scheduleWorkflow(objective, iso);
      setScheduledMsg(`Scheduled job ${r.job_id} for ${r.run_at}`);
    } catch (e) {
      setScheduledMsg((e as Error).message);
    }
  }

  async function submit() {
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

  async function resume() {
    if (!wf) return;
    setBusy(true);
    try {
      const w = await api.resume(wf.id);
      setWf(w);
      setTasks(await api.listTasks(w.id));
    } catch (e) {
      setErr((e as Error).message);
    } finally {
      setBusy(false);
    }
  }

  return (
    <div className="grid grid-cols-1 lg:grid-cols-3 gap-4">
      <div className="card p-4 lg:col-span-2">
        <div className="font-semibold mb-2">Tell the AI workforce what to do</div>
        <textarea
          className="input h-32"
          value={objective}
          onChange={(e) => setObjective(e.target.value)}
        />
        <div className="flex gap-2 mt-3">
          <button className="btn" disabled={busy} onClick={submit}>
            {busy ? "Working…" : "Submit"}
          </button>
          {wf && (
            <button className="btn-ghost" disabled={busy} onClick={resume}>
              Resume after approvals
            </button>
          )}
        </div>
        {err && <div className="text-bad text-sm mt-2">{err}</div>}
        <div className="mt-4 border-t border-line pt-3">
          <div className="text-sm font-semibold mb-1">Schedule for later</div>
          <input
            type="datetime-local"
            className="input max-w-xs"
            value={scheduleAt}
            onChange={(e) => setScheduleAt(e.target.value)}
          />
          <button className="btn-ghost ml-2" onClick={scheduleRun}>
            Schedule
          </button>
          {scheduledMsg && (
            <div className="text-xs text-muted mt-1">{scheduledMsg}</div>
          )}
        </div>
      </div>
      <div className="card p-4">
        <div className="font-semibold mb-2">Status</div>
        {!wf ? (
          <div className="text-muted text-sm">No workflow yet. Submit an objective.</div>
        ) : (
          <div>
            <div className="text-sm text-muted">Workflow</div>
            <div className="font-mono text-xs break-all">{wf.id}</div>
            <div className="mt-2">
              <span className={statePillClass(wf.state)}>{wf.state}</span>
            </div>
            <div className="mt-3 text-sm">
              {wf.plan?.tasks?.length ?? 0} planned tasks
            </div>
          </div>
        )}
      </div>
      {tasks.length > 0 && (
        <div className="card p-4 lg:col-span-3">
          <div className="font-semibold mb-2">Tasks</div>
          <table className="w-full text-sm">
            <thead className="text-muted text-left">
              <tr>
                <th className="py-2">Agent</th>
                <th>Title</th>
                <th>State</th>
                <th>Error</th>
              </tr>
            </thead>
            <tbody>
              {tasks.map((t) => (
                <tr key={t.id} className="border-t border-line">
                  <td className="py-2">{t.agent_name}</td>
                  <td>{t.title}</td>
                  <td>
                    <span className={statePillClass(t.state)}>{t.state}</span>
                  </td>
                  <td className="text-bad">{t.error ?? ""}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}
    </div>
  );
}
