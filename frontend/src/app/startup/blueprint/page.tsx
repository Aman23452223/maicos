"use client";

import { useEffect, useState } from "react";
import { api } from "@/lib/api";
import { useAuth } from "@/contexts/AuthContext";

export default function StartupBlueprint() {
  const { user } = useAuth();
  const [idea, setIdea] = useState("");
  const [sections, setSections] = useState<Record<string, { status: string; text: string }> | null>(null);
  const [saved, setSaved] = useState<{ id: string; status: string } | null>(null);
  const [list, setList] = useState<{ id: string; idea: string; status: string; sections: number }[]>([]);
  const [wsName, setWsName] = useState("");
  const [msg, setMsg] = useState<string | null>(null);

  async function refresh() {
    try {
      setList(await api.startupBlueprints());
    } catch {
      /* ignore */
    }
  }

  useEffect(() => {
    if (user) refresh();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [user]);

  async function handleGenerate() {
    try {
      const r = await api.companyBlueprint(idea);
      setSections(r.sections);
      setMsg("Review below. Assumptions are NOT facts.");
    } catch (e) {
      setMsg((e as Error).message);
    }
  }

  async function handleSave() {
    if (!sections) return;
    try {
      const r = await api.startupBlueprintSave(idea, sections);
      setSaved(r);
      refresh();
      setMsg(`Saved as draft (${r.id.slice(0, 8)}).`);
    } catch (e) {
      setMsg((e as Error).message);
    }
  }

  async function handleApprove(id: string) {
    await api.startupBlueprintApprove(id);
    refresh();
  }

  async function handleApply(id: string) {
    try {
      const r = await api.startupBlueprintApply(id);
      setMsg(`Applied: ${(r.goals_added as number) ?? 0} goals created.`);
      refresh();
    } catch (e) {
      setMsg((e as Error).message);
    }
  }

  async function handleCreateWorkspace() {
    const approved = list.find((b) => b.status === "applied" || b.status === "approved");
    try {
      const r = await api.startupCreateWorkspace(
        wsName || "My Startup", approved?.id || undefined,
      );
      setMsg(`Workspace "${r.name}" created. Switch to it from the top bar to operate it.`);
    } catch (e) {
      setMsg((e as Error).message);
    }
  }

  return (
    <div className="space-y-6">
      <div>
        <h1 className="text-2xl font-bold text-ink">📐 Startup Blueprint</h1>
        <p className="text-xs text-muted mt-1">Generate → review → approve → apply → create workspace. Nothing executes before approval.</p>
      </div>
      {msg && <div className="text-xs text-muted">{msg}</div>}

      <div className="p-5 rounded-2xl bg-[#0e1217] border border-white/[0.08] space-y-3">
        <input
          value={idea}
          onChange={(e) => setIdea(e.target.value)}
          placeholder="Startup idea…"
          className="w-full bg-black/40 border border-white/10 rounded-xl px-3 py-2 text-sm text-ink"
        />
        <div className="flex gap-2">
          <button onClick={handleGenerate} disabled={!idea.trim()} className="px-4 py-2 rounded-xl bg-accent text-bg text-xs font-semibold">
            Generate blueprint
          </button>
          {sections && (
            <button onClick={handleSave} className="px-4 py-2 rounded-xl bg-white/5 border border-white/10 text-xs">
              Save draft
            </button>
          )}
        </div>
      </div>

      {sections && (
        <div className="p-5 rounded-2xl bg-[#0e1217] border border-white/[0.08] text-xs space-y-1.5 max-h-96 overflow-y-auto">
          {Object.entries(sections).map(([k, v]) => (
            <div key={k} className="text-muted">
              <span className="text-ink font-medium">{k}</span>{" "}
              <span className="font-mono text-[10px]">[{v.status}]</span>
              <div>{v.text}</div>
            </div>
          ))}
        </div>
      )}

      <div className="p-5 rounded-2xl bg-[#0e1217] border border-white/[0.08] space-y-2">
        <div className="text-xs font-semibold text-ink">Saved blueprints</div>
        {list.map((b) => (
          <div key={b.id} className="flex items-center justify-between text-xs p-2 rounded-lg bg-black/40 border border-white/5">
            <span className="truncate">{b.idea} <span className="font-mono text-muted">[{b.status}]</span></span>
            <div className="flex gap-1.5">
              {b.status === "draft" && (
                <button onClick={() => handleApprove(b.id)} className="px-2 py-1 rounded bg-white/5 border border-white/10 text-[11px]">Approve</button>
              )}
              {b.status === "approved" && (
                <button onClick={() => handleApply(b.id)} className="px-2 py-1 rounded bg-ok text-bg text-[11px] font-semibold">Apply</button>
              )}
            </div>
          </div>
        ))}
        {list.length === 0 && <div className="text-[11px] text-muted">No blueprints yet.</div>}
      </div>

      <div className="p-5 rounded-2xl bg-[#0e1217] border border-white/[0.08] space-y-3">
        <div className="text-xs font-semibold text-ink">🏭 Create startup workspace</div>
        <div className="flex gap-2">
          <input
            value={wsName}
            onChange={(e) => setWsName(e.target.value)}
            placeholder="Startup workspace name"
            className="flex-1 bg-black/40 border border-white/10 rounded-xl px-3 py-2 text-sm text-ink"
          />
          <button onClick={handleCreateWorkspace} className="px-4 py-2 rounded-xl bg-accent text-bg text-xs font-semibold">
            Create
          </button>
        </div>
      </div>
    </div>
  );
}
