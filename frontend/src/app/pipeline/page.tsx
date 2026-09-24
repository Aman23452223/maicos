"use client";

import { useEffect, useState } from "react";
import { api } from "@/lib/api";
import { useAuth } from "@/contexts/AuthContext";

const STAGES = ["new", "contacted", "meeting", "proposal", "won", "lost"];

export default function PipelinePage() {
  const { user } = useAuth();
  const [opps, setOpps] = useState<{ id: string; title: string; amount: number; stage: string; status: string }[]>([]);
  const [msg, setMsg] = useState<string | null>(null);

  async function load() {
    try {
      setOpps(await api.listOpps());
    } catch (e) {
      setMsg((e as Error).message);
    }
  }

  useEffect(() => {
    if (user) load();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [user]);

  async function move(id: string, stage: string) {
    try {
      await api.patchOpp(id, { stage });
      load();
    } catch (e) {
      setMsg((e as Error).message);
    }
  }

  return (
    <div className="space-y-6">
      <div>
        <h1 className="text-2xl font-bold text-ink">Sales Pipeline</h1>
        <p className="text-xs text-muted mt-1">Move deals across stages. Real CRM data.</p>
      </div>
      {msg && <div className="text-xs text-muted">{msg}</div>}
      <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 gap-3">
        {STAGES.map((s) => (
          <div key={s} className="p-4 rounded-2xl bg-[#0e1217] border border-white/[0.08]">
            <div className="text-xs font-semibold text-ink uppercase mb-2">{s}</div>
            <div className="space-y-2">
              {opps.filter((o) => o.stage === s).map((o) => (
                <div key={o.id} className="p-2.5 rounded-xl bg-black/40 border border-white/5">
                  <div className="text-xs text-ink font-medium">{o.title}</div>
                  <div className="text-[11px] text-muted">₹{o.amount}</div>
                  <select
                    value={o.stage}
                    onChange={(e) => move(o.id, e.target.value)}
                    className="mt-1.5 w-full bg-black/60 border border-white/10 rounded px-1.5 py-1 text-[11px] text-ink"
                  >
                    {STAGES.map((x) => (
                      <option key={x} value={x}>{x}</option>
                    ))}
                  </select>
                </div>
              ))}
              {opps.filter((o) => o.stage === s).length === 0 && (
                <div className="text-[11px] text-muted">—</div>
              )}
            </div>
          </div>
        ))}
      </div>
    </div>
  );
}
