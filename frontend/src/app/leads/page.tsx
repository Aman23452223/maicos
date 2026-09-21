"use client";

import { useEffect, useState } from "react";
import { api } from "@/lib/api";
import type { Lead } from "@/lib/types";

export default function LeadsPage() {
  const [leads, setLeads] = useState<Lead[]>([]);
  const [status, setStatus] = useState("");
  const [query, setQuery] = useState("Find restaurants in Nagpur");
  const [msg, setMsg] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);

  async function load() {
    try {
      setLeads(await api.listLeads(status || undefined));
    } catch (e) {
      setMsg((e as Error).message);
    }
  }

  useEffect(() => {
    load();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [status]);

  async function handleDiscover() {
    setBusy(true);
    setMsg(null);
    try {
      const res = await api.discoverLeads(query);
      if (res.status === "NOT_CONFIGURED") {
        setMsg(`Discovery needs provider setup: ${res.message}`);
      } else {
        setMsg(`Found ${res.prospects.length} prospects`);
      }
    } catch (e) {
      setMsg((e as Error).message);
    } finally {
      setBusy(false);
    }
  }

  async function handleQualify(id: string) {
    try {
      const r = await api.qualifyLead(id);
      setMsg(`Lead scored ${r.score} → ${r.status}`);
      load();
    } catch (e) {
      setMsg((e as Error).message);
    }
  }

  return (
    <div className="space-y-6">
      <div>
        <h1 className="text-2xl font-bold text-ink">Leads &amp; CRM</h1>
        <p className="text-xs text-muted mt-1">Discovery → Import → Qualify → Follow-up. Real DB records, no fake leads.</p>
      </div>

      <div className="p-5 rounded-2xl bg-[#0e1217] border border-white/[0.08] space-y-3">
        <div className="text-xs font-semibold text-ink">🔍 Lead Discovery</div>
        <div className="flex gap-2">
          <input
            value={query}
            onChange={(e) => setQuery(e.target.value)}
            className="flex-1 bg-black/40 border border-white/10 rounded-xl px-3 py-2 text-sm text-ink"
            placeholder="Find restaurants in Nagpur"
          />
          <button
            onClick={handleDiscover}
            disabled={busy}
            className="px-4 py-2 rounded-xl bg-accent text-bg text-xs font-semibold disabled:opacity-50"
          >
            {busy ? "Searching…" : "Discover"}
          </button>
        </div>
        {msg && <div className="text-xs text-muted">{msg}</div>}
      </div>

      <div className="p-5 rounded-2xl bg-[#0e1217] border border-white/[0.08]">
        <div className="flex items-center justify-between mb-3">
          <div className="text-xs font-semibold text-ink">📋 Leads ({leads.length})</div>
          <select
            value={status}
            onChange={(e) => setStatus(e.target.value)}
            className="bg-black/40 border border-white/10 rounded-lg px-2 py-1 text-xs text-ink"
          >
            <option value="">All</option>
            <option value="NEW">New</option>
            <option value="QUALIFIED">Qualified</option>
            <option value="CONTACTED">Contacted</option>
            <option value="RESPONDED">Responded</option>
            <option value="MEETING">Meeting</option>
            <option value="WON">Won</option>
            <option value="LOST">Lost</option>
          </select>
        </div>
        <div className="overflow-x-auto">
          <table className="w-full text-xs text-left">
            <thead className="text-muted border-b border-white/[0.08]">
              <tr>
                <th className="py-2">Company</th>
                <th>Email</th>
                <th>Location</th>
                <th>Score</th>
                <th>Status</th>
                <th></th>
              </tr>
            </thead>
            <tbody className="divide-y divide-white/5">
              {leads.map((l) => (
                <tr key={l.id}>
                  <td className="py-2 text-ink font-medium">{l.company_name}</td>
                  <td className="text-muted">{l.email || "—"}</td>
                  <td className="text-muted">{l.location || "—"}</td>
                  <td className="font-mono text-ink">{l.score}</td>
                  <td className="text-muted">{l.status}</td>
                  <td>
                    <button
                      onClick={() => handleQualify(l.id)}
                      className="px-2 py-1 rounded-md bg-white/5 border border-white/10 text-[11px] hover:bg-white/10"
                    >
                      Qualify
                    </button>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
          {leads.length === 0 && <div className="text-[11px] text-muted py-6 text-center">No leads yet. Import via Command Center or API.</div>}
        </div>
      </div>
    </div>
  );
}
