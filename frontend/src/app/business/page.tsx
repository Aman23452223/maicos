"use client";

import { useEffect, useState } from "react";
import { api } from "@/lib/api";
import { useAuth } from "@/contexts/AuthContext";

export default function BusinessPage() {
  const { user } = useAuth();
  const [profile, setProfile] = useState<Record<string, unknown> | null>(null);
  const [goals, setGoals] = useState<{ id: string; text: string; status: string }[]>([]);
  const [newGoal, setNewGoal] = useState("");
  const [msg, setMsg] = useState<string | null>(null);
  const [name, setName] = useState("");
  const [industry, setIndustry] = useState("");

  async function load() {
    try {
      const p = await api.getBusinessProfile();
      setProfile(p as unknown as Record<string, unknown>);
      setName(String((p as unknown as Record<string, unknown>).business_name || ""));
      setIndustry(String((p as unknown as Record<string, unknown>).industry || ""));
      setGoals(await api.listGoals());
    } catch (e) {
      setMsg((e as Error).message);
    }
  }

  useEffect(() => {
    if (user) load();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [user]);

  async function saveProfile() {
    try {
      await api.updateBusinessProfile({ business_name: name, industry });
      setMsg("Business profile saved.");
      load();
    } catch (e) {
      setMsg((e as Error).message);
    }
  }

  async function addGoal() {
    if (!newGoal.trim()) return;
    try {
      await api.addGoal(newGoal.trim());
      setNewGoal("");
      setGoals(await api.listGoals());
    } catch (e) {
      setMsg((e as Error).message);
    }
  }

  return (
    <div className="space-y-6">
      <div>
        <h1 className="text-2xl font-bold text-ink">Business Profile</h1>
        <p className="text-xs text-muted mt-1">
          Workspace context the AI Manager plans from: identity, goals, ICP. No industry-specific code.
        </p>
      </div>
      {msg && <div className="text-xs text-muted">{msg}</div>}

      <div className="p-5 rounded-2xl bg-[#0e1217] border border-white/[0.08] space-y-3">
        <div className="text-xs font-semibold text-ink">🏢 Identity</div>
        <input
          value={name}
          onChange={(e) => setName(e.target.value)}
          placeholder="Business name"
          className="w-full bg-black/40 border border-white/10 rounded-xl px-3 py-2 text-sm text-ink"
        />
        <input
          value={industry}
          onChange={(e) => setIndustry(e.target.value)}
          placeholder="Industry (free text)"
          className="w-full bg-black/40 border border-white/10 rounded-xl px-3 py-2 text-sm text-ink"
        />
        <button
          onClick={saveProfile}
          className="px-4 py-2 rounded-xl bg-accent text-bg text-xs font-semibold"
        >
          Save Profile
        </button>
      </div>

      <div className="p-5 rounded-2xl bg-[#0e1217] border border-white/[0.08] space-y-3">
        <div className="text-xs font-semibold text-ink">🎯 Business Goals</div>
        <div className="flex gap-2">
          <input
            value={newGoal}
            onChange={(e) => setNewGoal(e.target.value)}
            placeholder="e.g. Acquire 100 customers this quarter"
            className="flex-1 bg-black/40 border border-white/10 rounded-xl px-3 py-2 text-sm text-ink"
          />
          <button
            onClick={addGoal}
            className="px-4 py-2 rounded-xl bg-accent text-bg text-xs font-semibold"
          >
            Add
          </button>
        </div>
        <div className="space-y-1.5">
          {goals.map((g) => (
            <div key={g.id} className="flex items-center justify-between text-xs p-2 rounded-lg bg-black/40 border border-white/5">
              <span className="text-ink">{g.text}</span>
              <button
                onClick={() => api.deleteGoal(g.id).then(() => api.listGoals()).then(setGoals)}
                className="text-bad hover:underline text-[11px]"
              >
                Remove
              </button>
            </div>
          ))}
          {goals.length === 0 && <div className="text-[11px] text-muted">No goals yet.</div>}
        </div>
      </div>

      {profile && (
        <div className="p-5 rounded-2xl bg-[#0e1217] border border-white/[0.08] text-xs text-muted space-y-1">
          <div className="font-semibold text-ink">Derived context</div>
          <div>Target: {String(profile.target_customer || "—").slice(0, 200)}</div>
          <div>Geography: {String(profile.geography || "—")}</div>
          <div>Website: {String(profile.website_url || "—")}</div>
        </div>
      )}
    </div>
  );
}
