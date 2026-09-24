"use client";

import { useEffect, useState } from "react";
import { api } from "@/lib/api";
import { useAuth } from "@/contexts/AuthContext";

export default function TasksPage() {
  const { user } = useAuth();
  const [mine, setMine] = useState<{ id: string; title: string; state: string; due_at: string | null }[]>([]);
  const [team, setTeam] = useState<{ id: string; name: string; email: string }[]>([]);
  const [title, setTitle] = useState("");
  const [assignee, setAssignee] = useState("");
  const [msg, setMsg] = useState<string | null>(null);

  async function load() {
    try {
      setMine(await api.myTasks());
      setTeam(await api.team());
    } catch (e) {
      setMsg((e as Error).message);
    }
  }

  useEffect(() => {
    if (user) load();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [user]);

  async function assign() {
    if (!title.trim()) return;
    try {
      await api.createStaffTask(title.trim(), assignee || undefined);
      setTitle("");
      setAssignee("");
      setMsg("Task assigned.");
    } catch (e) {
      setMsg((e as Error).message);
    }
  }

  async function setState(id: string, state: string) {
    try {
      await api.staffTaskState(id, state);
      load();
    } catch (e) {
      setMsg((e as Error).message);
    }
  }

  return (
    <div className="space-y-6">
      <div>
        <h1 className="text-2xl font-bold text-ink">My Tasks</h1>
        <p className="text-xs text-muted mt-1">Human teamwork — assign, do, mark done.</p>
      </div>
      {msg && <div className="text-xs text-muted">{msg}</div>}

      <div className="p-5 rounded-2xl bg-[#0e1217] border border-white/[0.08] space-y-3">
        <div className="text-xs font-semibold text-ink">➕ Assign task</div>
        <div className="flex flex-col sm:flex-row gap-2">
          <input
            value={title}
            onChange={(e) => setTitle(e.target.value)}
            placeholder="e.g. Call Sharma ji for payment"
            className="flex-1 bg-black/40 border border-white/10 rounded-xl px-3 py-2 text-sm text-ink"
          />
          <select value={assignee} onChange={(e) => setAssignee(e.target.value)} className="bg-black/40 border border-white/10 rounded-xl px-2 text-xs text-ink">
            <option value="">Unassigned</option>
            {team.map((t) => (
              <option key={t.id} value={t.id}>{t.name} ({t.email})</option>
            ))}
          </select>
          <button onClick={assign} className="px-4 py-2 rounded-xl bg-accent text-bg text-xs font-semibold">Assign</button>
        </div>
      </div>

      <div className="p-5 rounded-2xl bg-[#0e1217] border border-white/[0.08] space-y-2">
        <div className="text-xs font-semibold text-ink">📋 My tasks ({mine.length})</div>
        {mine.map((t) => (
          <div key={t.id} className="flex items-center justify-between gap-2 p-2 rounded-lg bg-black/40 border border-white/5 text-xs">
            <span className={t.state === "COMPLETED" ? "line-through text-muted" : "text-ink"}>{t.title}</span>
            <div className="flex gap-1.5">
              {t.state !== "COMPLETED" ? (
                <button onClick={() => setState(t.id, "COMPLETED")} className="px-2 py-1 rounded bg-ok text-bg text-[11px] font-semibold">Done</button>
              ) : (
                <button onClick={() => setState(t.id, "PENDING")} className="px-2 py-1 rounded bg-white/5 border border-white/10 text-[11px]">Reopen</button>
              )}
            </div>
          </div>
        ))}
        {mine.length === 0 && <div className="text-[11px] text-muted">No tasks assigned to you.</div>}
      </div>
    </div>
  );
}
