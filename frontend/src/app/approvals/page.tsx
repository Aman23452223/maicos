"use client";

import { useEffect, useState, useCallback } from "react";
import { api } from "@/lib/api";
import { useAuth } from "@/contexts/AuthContext";
import type { Approval, WorkflowTask } from "@/lib/types";

export default function ApprovalsPage() {
  const { user, status, openAuthModal } = useAuth();
  const [items, setItems] = useState<Approval[]>([]);
  const [filter, setFilter] = useState<"ALL" | "PENDING" | "APPROVED" | "REJECTED">("PENDING");
  const [loading, setLoading] = useState(false);
  const [err, setErr] = useState<string | null>(null);
  const [decidingId, setDecidingId] = useState<string | null>(null);
  const [answers, setAnswers] = useState<Record<string, string>>({});
  const [planTasks, setPlanTasks] = useState<Record<string, WorkflowTask[]>>({});
  const [editing, setEditing] = useState<Record<string, { id: string; title: string; description: string }>>({});

  async function loadPlanTasks(approvalId: string, workflowId: string) {
    try {
      const ts = await api.listTasks(workflowId);
      setPlanTasks((m) => ({ ...m, [approvalId]: ts }));
    } catch {
      /* ignore */
    }
  }

  async function handleSaveTask(approvalId: string, workflowId: string, taskId: string) {
    const e = editing[`${approvalId}:${taskId}`];
    if (!e) return;
    try {
      await api.patchTask(workflowId, taskId, { title: e.title, description: e.description });
      setEditing((m) => {
        const n = { ...m };
        delete n[`${approvalId}:${taskId}`];
        return n;
      });
      loadPlanTasks(approvalId, workflowId);
    } catch (err) {
      setErr((err as Error).message);
    }
  }

  async function handleAnswer(id: string) {
    const note = (answers[id] || "").trim();
    if (!note) {
      setErr("Pehle jawab likho, phir Send dabao.");
      return;
    }
    setDecidingId(id);
    setErr(null);
    try {
      await api.decide(id, "APPROVE", note);
      setAnswers((a) => {
        const n = { ...a };
        delete n[id];
        return n;
      });
      await refresh();
    } catch (e) {
      setErr((e as Error).message);
    } finally {
      setDecidingId(null);
    }
  }

  const refresh = useCallback(async () => {
    if (!user) return;
    setLoading(true);
    setErr(null);
    try {
      const data = await api.listApprovals();
      setItems(data);
    } catch (e) {
      const msg = (e as Error).message;
      if (!msg.includes("401") && !msg.includes("bearer")) {
        setErr(msg);
      }
    } finally {
      setLoading(false);
    }
  }, [user]);

  useEffect(() => {
    if (user) {
      refresh();
    }
  }, [user, refresh]);

  async function handleDecision(id: string, decision: "APPROVE" | "REJECT") {
    setDecidingId(id);
    setErr(null);
    try {
      await api.decide(id, decision);
      await refresh();
    } catch (e) {
      setErr((e as Error).message);
    } finally {
      setDecidingId(null);
    }
  }

  // If user is not authenticated, show a sleek workspace sign-in gate
  if (status === "anon" || (!user && status !== "loading")) {
    return (
      <div className="max-w-2xl mx-auto py-12 px-4 text-center">
        <div className="w-16 h-16 mx-auto mb-6 rounded-2xl bg-gradient-to-tr from-accent/20 to-purple-500/20 border border-accent/30 flex items-center justify-center text-2xl shadow-[0_0_30px_rgba(91,141,239,0.2)]">
          🛡️
        </div>
        <h1 className="text-2xl font-bold tracking-tight text-ink mb-2">
          Autonomous Governance & Approval Center
        </h1>
        <p className="text-sm text-muted max-w-md mx-auto mb-8">
          Critical operations such as API mutations, financial transfers, and live system modifications require human authorization. Sign in to review and approve tasks.
        </p>
        <div className="flex flex-col sm:flex-row items-center justify-center gap-3">
          <button
            onClick={() => openAuthModal("signin")}
            className="w-full sm:w-auto px-6 py-2.5 rounded-xl bg-accent hover:bg-accent/90 text-bg font-semibold text-sm shadow-[0_0_20px_rgba(91,141,239,0.4)] transition-all"
          >
            Sign in to Workspace
          </button>
          <button
            onClick={() => openAuthModal("signup")}
            className="w-full sm:w-auto px-6 py-2.5 rounded-xl bg-white/5 hover:bg-white/10 text-ink border border-white/10 text-sm font-medium transition-all"
          >
            Create Workspace Account
          </button>
        </div>
      </div>
    );
  }

  const filteredItems = items.filter((a) => {
    if (filter === "ALL") return true;
    return a.status === filter;
  });

  const counts = {
    pending: items.filter((a) => a.status === "PENDING").length,
    approved: items.filter((a) => a.status === "APPROVED").length,
    rejected: items.filter((a) => a.status === "REJECTED").length,
  };

  return (
    <div className="space-y-6">
      {/* Header & Controls */}
      <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-4">
        <div>
          <h1 className="text-xl font-bold tracking-tight text-ink flex items-center gap-2">
            <span>🛡️</span>
            <span>Approval Center</span>
          </h1>
          <p className="text-xs text-muted mt-0.5">
            Review and authorize critical actions delegated to autonomous agents.
          </p>
        </div>

        <div className="flex items-center gap-2">
          <button
            onClick={refresh}
            disabled={loading}
            className="px-3 py-1.5 rounded-lg bg-white/5 hover:bg-white/10 border border-white/10 text-xs text-muted hover:text-ink transition-colors flex items-center gap-1.5"
          >
            <span className={loading ? "animate-spin" : ""}>🔄</span>
            <span>Refresh</span>
          </button>
        </div>
      </div>

      {/* Filter Tabs & Stats */}
      <div className="flex flex-wrap items-center justify-between gap-3 border-b border-white/[0.08] pb-3">
        <div className="flex items-center gap-1.5">
          {(
            [
              { id: "PENDING", label: "Pending", count: counts.pending },
              { id: "ALL", label: "All Events", count: items.length },
              { id: "APPROVED", label: "Approved", count: counts.approved },
              { id: "REJECTED", label: "Rejected", count: counts.rejected },
            ] as const
          ).map((tab) => (
            <button
              key={tab.id}
              onClick={() => setFilter(tab.id)}
              className={`px-3 py-1.5 rounded-lg text-xs font-medium transition-all flex items-center gap-1.5 ${
                filter === tab.id
                  ? "bg-accent/15 text-white border border-accent/30 font-semibold"
                  : "text-muted hover:text-ink hover:bg-white/[0.04]"
              }`}
            >
              <span>{tab.label}</span>
              <span
                className={`px-1.5 py-0.2 rounded-full text-[10px] ${
                  filter === tab.id
                    ? "bg-accent/25 text-white"
                    : "bg-white/5 text-muted"
                }`}
              >
                {tab.count}
              </span>
            </button>
          ))}
        </div>
      </div>

      {/* Error display */}
      {err && (
        <div className="p-3.5 rounded-xl bg-bad/10 border border-bad/30 text-bad text-xs flex items-center justify-between">
          <span>{err}</span>
          <button onClick={() => setErr(null)} className="text-bad hover:underline font-bold">
            Dismiss
          </button>
        </div>
      )}

      {/* Approval Items List */}
      {filteredItems.length === 0 ? (
        <div className="p-12 text-center rounded-2xl bg-white/[0.02] border border-white/[0.06]">
          <div className="w-12 h-12 mx-auto mb-3 rounded-full bg-ok/10 border border-ok/20 flex items-center justify-center text-xl text-ok">
            ✓
          </div>
          <h3 className="text-sm font-semibold text-ink">All Clear!</h3>
          <p className="text-xs text-muted max-w-sm mx-auto mt-1">
            {filter === "PENDING"
              ? "There are no actions currently waiting for approval. Your agents are operating smoothly."
              : `No approvals found in "${filter}" status.`}
          </p>
        </div>
      ) : (
        <div className="grid grid-cols-1 gap-3.5">
          {filteredItems.map((a) => {
            const isPending = a.status === "PENDING";
            const isDeciding = decidingId === a.id;
            const isPlanReview = a.action === "plan_review";
            if (isPending && isPlanReview && !planTasks[a.id]) {
              loadPlanTasks(a.id, a.workflow_id);
            }

            return (
              <div
                key={a.id}
                className="p-4 rounded-xl bg-[#0e1217] border border-white/[0.08] hover:border-white/[0.15] transition-all flex flex-col md:flex-row md:items-center justify-between gap-4 shadow-sm"
              >
                <div className="space-y-1.5 flex-1 min-w-0">
                  <div className="flex items-center gap-2 flex-wrap">
                    <span className="px-2 py-0.5 rounded-md bg-white/[0.05] border border-white/10 text-xs font-mono text-ink font-semibold">
                      {a.action}
                    </span>
                    <span className="text-xs text-muted/60">→</span>
                    <span className="px-2 py-0.5 rounded-md bg-blue-500/10 text-blue-400 border border-blue-500/20 text-xs font-mono">
                      {a.target_system}
                    </span>
                    <span
                      className={`px-2 py-0.5 rounded-full text-[10px] font-bold uppercase tracking-wider ${
                        a.status === "APPROVED"
                          ? "bg-ok/10 text-ok border border-ok/20"
                          : a.status === "REJECTED"
                          ? "bg-bad/10 text-bad border border-bad/20"
                          : "bg-warn/10 text-warn border border-warn/20 animate-pulse"
                      }`}
                    >
                      {a.status}
                    </span>
                  </div>

                  <p className="text-sm text-ink/90 font-normal leading-relaxed break-words">
                    {a.description}
                  </p>

                  <div className="flex items-center gap-3 text-xs text-muted">
                    <span>
                      Requested by: <strong className="text-ink font-mono">{a.requested_by_agent}</strong>
                    </span>
                    <span>•</span>
                    <span className="font-mono text-[11px] text-muted/60">ID: {a.id.slice(0, 8)}…</span>
                  </div>
                </div>

                {/* Plan review: inspect + edit tasks, then approve to run */}
                {isPlanReview && (
                  <div className="p-3 rounded-lg bg-accent/5 border border-accent/20 space-y-2">
                    <div className="text-xs text-ink font-semibold">
                      📋 Plan review — steps check karo, edit karo, phir Approve dabao (tabhi chalega):
                    </div>
                    {(planTasks[a.id] || []).map((t) => {
                      const key = `${a.id}:${t.id}`;
                      const ed = editing[key];
                      return (
                        <div key={t.id} className="p-2 rounded-md bg-black/40 border border-white/10 space-y-1">
                          {ed ? (
                            <>
                              <input
                                value={ed.title}
                                onChange={(e) => setEditing({ ...editing, [key]: { ...ed, title: e.target.value } })}
                                className="w-full bg-black/60 border border-white/10 rounded px-2 py-1 text-xs text-ink"
                              />
                              <input
                                value={ed.description}
                                onChange={(e) => setEditing({ ...editing, [key]: { ...ed, description: e.target.value } })}
                                className="w-full bg-black/60 border border-white/10 rounded px-2 py-1 text-[11px] text-muted"
                              />
                              <button
                                onClick={() => handleSaveTask(a.id, a.workflow_id, t.id)}
                                className="px-3 py-1 rounded-md bg-ok text-bg text-[11px] font-semibold"
                              >
                                Save step
                              </button>
                            </>
                          ) : (
                            <div className="flex items-center justify-between gap-2">
                              <div className="text-xs">
                                <span className="font-mono text-accent">🤖 {t.agent_name}</span>
                                <span className="text-ink"> — {t.title}</span>
                              </div>
                              {isPending && (
                                <button
                                  onClick={() =>
                                    setEditing({ ...editing, [key]: { id: t.id, title: t.title, description: t.description } })
                                  }
                                  className="px-2 py-0.5 rounded bg-white/5 border border-white/10 text-[11px] hover:bg-white/10"
                                >
                                  Edit
                                </button>
                              )}
                            </div>
                          )}
                        </div>
                      );
                    })}
                  </div>
                )}

                {/* Clarification question from agent */}
                {a.action === "input_required" && (
                  <div className="p-3 rounded-lg bg-accent/5 border border-accent/20 space-y-2">
                    <div className="text-xs text-ink font-medium">❓ Agent puch raha hai — jawab do, kaam aage badhega:</div>
                    {isPending ? (
                      <div className="flex gap-2">
                        <input
                          value={answers[a.id] || ""}
                          onChange={(e) => setAnswers({ ...answers, [a.id]: e.target.value })}
                          placeholder="Yaha jawab likho…"
                          className="flex-1 bg-black/40 border border-white/10 rounded-lg px-3 py-2 text-xs text-ink"
                        />
                        <button
                          onClick={() => handleAnswer(a.id)}
                          disabled={isDeciding}
                          className="px-4 py-2 rounded-lg bg-accent text-bg font-semibold text-xs disabled:opacity-50"
                        >
                          {isDeciding ? "Sending…" : "Send Answer"}
                        </button>
                        <button
                          onClick={() => handleDecision(a.id, "REJECT")}
                          disabled={isDeciding}
                          className="px-3 py-2 rounded-lg text-bad text-xs hover:underline disabled:opacity-50"
                        >
                          Cancel task
                        </button>
                      </div>
                    ) : (
                      <div className="text-xs text-muted">Resolved</div>
                    )}
                  </div>
                )}

                {/* Decision Actions */}
                <div className="flex items-center gap-2 self-end md:self-center flex-shrink-0">
                  {isPending && a.action !== "input_required" ? (
                    <>
                      <button
                        onClick={() => handleDecision(a.id, "APPROVE")}
                        disabled={isDeciding}
                        className="px-4 py-2 rounded-lg bg-ok hover:bg-ok/90 text-black font-semibold text-xs transition-all shadow-[0_0_12px_rgba(63,185,80,0.3)] disabled:opacity-50"
                      >
                        {isDeciding ? "Processing…" : "✓ Approve"}
                      </button>
                      <button
                        onClick={() => handleDecision(a.id, "REJECT")}
                        disabled={isDeciding}
                        className="px-4 py-2 rounded-lg bg-bad/15 hover:bg-bad/25 text-bad border border-bad/30 font-semibold text-xs transition-all disabled:opacity-50"
                      >
                        ✕ Reject
                      </button>
                    </>
                  ) : (
                    <div className="text-xs text-muted/60 font-mono">
                      Resolved
                    </div>
                  )}
                </div>
              </div>
            );
          })}
        </div>
      )}
    </div>
  );
}
