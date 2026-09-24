"use client";

import { useEffect, useState } from "react";
import { api } from "@/lib/api";
import { useAuth } from "@/contexts/AuthContext";

type Thread = {
  lead_id: string | null;
  from: string;
  name: string;
  channel: string;
  messages: { body: string; classification: string; at: string | null }[];
};

export default function InboxPage() {
  const { user } = useAuth();
  const [threads, setThreads] = useState<Thread[]>([]);
  const [sel, setSel] = useState<number>(0);
  const [reply, setReply] = useState("");
  const [msg, setMsg] = useState<string | null>(null);

  async function load() {
    try {
      setThreads(await api.inbox());
    } catch (e) {
      setMsg((e as Error).message);
    }
  }

  useEffect(() => {
    if (user) load();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [user]);

  async function send() {
    const t = threads[sel];
    if (!t || !reply.trim()) return;
    try {
      await api.inboxReply(t.lead_id, t.from, reply.trim());
      setReply("");
      setMsg("Reply sent.");
      load();
    } catch (e) {
      setMsg((e as Error).message);
    }
  }

  const t = threads[sel];

  return (
    <div className="space-y-6">
      <div>
        <h1 className="text-2xl font-bold text-ink">Support Inbox</h1>
        <p className="text-xs text-muted mt-1">All customer messages in one place. Replies honor sending policy.</p>
      </div>
      {msg && <div className="text-xs text-muted">{msg}</div>}
      <div className="grid grid-cols-1 lg:grid-cols-3 gap-3">
        <div className="p-4 rounded-2xl bg-[#0e1217] border border-white/[0.08] space-y-1.5">
          {threads.map((th, i) => (
            <button
              key={i}
              onClick={() => { setSel(i); setReply(""); }}
              className={`w-full text-left p-2.5 rounded-xl border text-xs ${i === sel ? "bg-accent/10 border-accent/30" : "bg-black/40 border-white/5"}`}
            >
              <div className="text-ink font-medium truncate">{th.name}</div>
              <div className="text-muted text-[11px] truncate">{th.messages[th.messages.length - 1]?.body}</div>
            </button>
          ))}
          {threads.length === 0 && <div className="text-[11px] text-muted">No conversations yet.</div>}
        </div>
        <div className="lg:col-span-2 p-4 rounded-2xl bg-[#0e1217] border border-white/[0.08] flex flex-col">
          {!t ? (
            <div className="text-xs text-muted">Select a conversation.</div>
          ) : (
            <>
              <div className="text-xs font-semibold text-ink mb-2">{t.name} <span className="text-muted font-normal">({t.channel})</span></div>
              <div className="space-y-2 flex-1 max-h-96 overflow-y-auto">
                {t.messages.map((m, i) => (
                  <div key={i} className="p-2.5 rounded-xl bg-black/40 border border-white/5 text-xs">
                    <div className="text-ink">{m.body}</div>
                    <div className="text-[10px] text-muted mt-1">{m.classification}</div>
                  </div>
                ))}
              </div>
              <div className="flex gap-2 mt-3">
                <input
                  value={reply}
                  onChange={(e) => setReply(e.target.value)}
                  placeholder="Type reply…"
                  className="flex-1 bg-black/40 border border-white/10 rounded-xl px-3 py-2 text-sm text-ink"
                />
                <button onClick={send} className="px-4 py-2 rounded-xl bg-accent text-bg text-xs font-semibold">Send</button>
              </div>
            </>
          )}
        </div>
      </div>
    </div>
  );
}
