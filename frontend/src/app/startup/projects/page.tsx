"use client";

import { useEffect, useState } from "react";
import { api } from "@/lib/api";
import { useAuth } from "@/contexts/AuthContext";

export default function StartupProjects() {
  const { user } = useAuth();
  const [roles, setRoles] = useState<{ id: string; title: string; kind: string; status: string }[]>([]);
  const [title, setTitle] = useState("");
  const [kind, setKind] = useState("ai");

  async function load() {
    try {
      setRoles(await api.startupRoles());
    } catch {
      /* ignore */
    }
  }

  useEffect(() => {
    if (user) load();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [user]);

  async function add() {
    if (!title.trim()) return;
    await api.startupRoleAdd(title.trim(), kind);
    setTitle("");
    load();
  }

  const ai = roles.filter((r) => r.kind === "ai");
  const human = roles.filter((r) => r.kind === "human");

  return (
    <div className="space-y-6">
      <div>
        <h1 className="text-2xl font-bold text-ink">👥 Projects & Workforce Roles</h1>
        <p className="text-xs text-muted mt-1">
          AI roles execute digitally. Human roles need hiring + approval — MAICOS never auto-hires.
        </p>
      </div>

      <div className="p-5 rounded-2xl bg-[#0e1217] border border-white/[0.08] space-y-3">
        <div className="flex gap-2">
          <input
            value={title}
            onChange={(e) => setTitle(e.target.value)}
            placeholder="e.g. Delivery Partner, Backend Engineer"
            className="flex-1 bg-black/40 border border-white/10 rounded-xl px-3 py-2 text-sm text-ink"
          />
          <select value={kind} onChange={(e) => setKind(e.target.value)} className="bg-black/40 border border-white/10 rounded-xl px-2 text-xs text-ink">
            <option value="ai">AI role</option>
            <option value="human">Human role</option>
          </select>
          <button onClick={add} className="px-4 py-2 rounded-xl bg-accent text-bg text-xs font-semibold">Add</button>
        </div>
      </div>

      <div className="grid grid-cols-1 md:grid-cols-2 gap-3">
        <div className="p-5 rounded-2xl bg-[#0e1217] border border-white/[0.08]">
          <div className="text-xs font-semibold text-ink mb-2">🤖 AI roles ({ai.length})</div>
          {ai.map((r) => <div key={r.id} className="text-xs text-muted py-1">• {r.title} [{r.status}]</div>)}
          {ai.length === 0 && <div className="text-[11px] text-muted">None yet.</div>}
        </div>
        <div className="p-5 rounded-2xl bg-[#0e1217] border border-white/[0.08]">
          <div className="text-xs font-semibold text-ink mb-2">🧑 Human roles ({human.length})</div>
          {human.map((r) => <div key={r.id} className="text-xs text-muted py-1">• {r.title} [{r.status}] — hiring needs approval</div>)}
          {human.length === 0 && <div className="text-[11px] text-muted">None yet.</div>}
        </div>
      </div>
    </div>
  );
}
