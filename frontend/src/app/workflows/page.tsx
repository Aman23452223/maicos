"use client";

import { useState } from "react";
import useSWR from "swr";
import { api } from "@/lib/api";
import { useAuth } from "@/contexts/AuthContext";
import { useRealtime } from "@/lib/realtime";
import type { Workflow, WorkflowState } from "@/lib/types";

const STATE_FILTERS: { label: string; value: WorkflowState | "" }[] = [
  { label: "All Workflows", value: "" },
  { label: "Running", value: "RUNNING" },
  { label: "Waiting Approval", value: "WAITING_APPROVAL" },
  { label: "Completed", value: "COMPLETED" },
  { label: "Failed", value: "FAILED" },
];

export default function WorkflowsPage() {
  const { user, openAuthModal } = useAuth();
  const [filter, setFilter] = useState<WorkflowState | "">("");
  const [selectedWorkflow, setSelectedWorkflow] = useState<Workflow | null>(null);

  const key = user ? `workflows-${filter || "all"}` : null;
  const { data, error, mutate } = useSWR<Workflow[]>(key, () =>
    api.listWorkflows(filter || undefined)
  );

  const realtime = useRealtime<Workflow>("workflows");
  const workflows =
    realtime.status === "ready" && realtime.data.length > 0
      ? realtime.data
      : (data ?? []);

  const filteredWorkflows = filter
    ? workflows.filter((w) => w.state === filter)
    : workflows;

  if (!user) {
    return (
      <div className="max-w-2xl mx-auto py-12 px-4 text-center">
        <div className="w-16 h-16 mx-auto mb-6 rounded-2xl bg-gradient-to-tr from-accent/20 to-blue-500/20 border border-accent/30 flex items-center justify-center text-2xl shadow-[0_0_30px_rgba(91,141,239,0.2)]">
          🔁
        </div>
        <h1 className="text-2xl font-bold tracking-tight text-ink mb-2">
          Autonomous Workflow Pipelines
        </h1>
        <p className="text-sm text-muted max-w-md mx-auto mb-8">
          Workflows orchestrate multiple agents across marketing, billing, dev, and compliance. Sign in to view and trigger workflows.
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

  return (
    <div className="space-y-6">
      {/* Page Header */}
      <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-4">
        <div>
          <h1 className="text-xl font-bold tracking-tight text-ink flex items-center gap-2">
            <span>🔁</span>
            <span>Workflows Engine</span>
          </h1>
          <p className="text-xs text-muted mt-0.5">
            Monitor real-time task DAGs, agent delegations, and autonomous state machines.
          </p>
        </div>

        {/* Live Channel Status */}
        <div className="flex items-center gap-2">
          <span className="text-xs text-muted">
            Live Stream:{" "}
            <span className={realtime.status === "ready" ? "text-ok font-mono" : "text-muted font-mono"}>
              {realtime.status === "ready" ? "● Connected" : "○ Polling"}
            </span>
          </span>
          <button
            onClick={() => mutate()}
            className="px-3 py-1.5 rounded-lg bg-white/5 hover:bg-white/10 border border-white/10 text-xs text-muted hover:text-ink transition-colors"
          >
            Refresh
          </button>
        </div>
      </div>

      {/* Filter Tabs */}
      <div className="flex flex-wrap items-center gap-1.5 border-b border-white/[0.08] pb-3">
        {STATE_FILTERS.map((f) => (
          <button
            key={f.value || "all"}
            onClick={() => setFilter(f.value)}
            className={`px-3 py-1.5 text-xs rounded-lg transition-all ${
              filter === f.value
                ? "bg-accent/15 text-white border border-accent/30 font-semibold"
                : "text-muted hover:text-ink hover:bg-white/[0.04]"
            }`}
          >
            {f.label}
          </button>
        ))}
      </div>

      {/* Grid: Left List (2 cols) + Right Detail (1 col) */}
      <div className="grid grid-cols-1 lg:grid-cols-3 gap-6">
        {/* Workflows List */}
        <div className="lg:col-span-2 space-y-3">
          {filteredWorkflows.length === 0 ? (
            <div className="p-12 text-center rounded-2xl bg-[#0e1217] border border-white/[0.08]">
              <div className="w-12 h-12 mx-auto mb-3 rounded-full bg-white/[0.04] flex items-center justify-center text-xl text-muted">
                🔁
              </div>
              <h3 className="text-sm font-semibold text-ink">No workflows found</h3>
              <p className="text-xs text-muted mt-1 max-w-sm mx-auto">
                No active workflows in this category. Go to the AI Command Center to kick off your first autonomous workflow.
              </p>
            </div>
          ) : (
            filteredWorkflows.map((w) => {
              const isSelected = selectedWorkflow?.id === w.id;
              return (
                <div
                  key={w.id}
                  onClick={() => setSelectedWorkflow(w)}
                  className={`p-4 rounded-xl border transition-all cursor-pointer ${
                    isSelected
                      ? "bg-accent/10 border-accent/40 shadow-[0_0_15px_rgba(91,141,239,0.15)]"
                      : "bg-[#0e1217] border-white/[0.08] hover:border-white/[0.15] hover:bg-white/[0.02]"
                  }`}
                >
                  <div className="flex items-center justify-between gap-3 mb-2">
                    <span className="font-semibold text-sm text-ink truncate flex-1">
                      {w.title}
                    </span>
                    <span
                      className={`px-2 py-0.5 rounded-full text-[10px] font-bold uppercase tracking-wider ${
                        w.state === "COMPLETED"
                          ? "bg-ok/10 text-ok border border-ok/20"
                          : w.state === "FAILED"
                          ? "bg-bad/10 text-bad border border-bad/20"
                          : w.state === "WAITING_APPROVAL"
                          ? "bg-warn/10 text-warn border border-warn/20 animate-pulse"
                          : "bg-accent/10 text-accent border border-accent/20 animate-pulse"
                      }`}
                    >
                      {w.state}
                    </span>
                  </div>

                  <p className="text-xs text-muted line-clamp-2 mb-3 leading-relaxed">
                    {w.objective}
                  </p>

                  <div className="flex items-center justify-between text-[11px] text-muted/70 pt-2 border-t border-white/5 font-mono">
                    <span>ID: {w.id.slice(0, 8)}…</span>
                    <span>Updated: {new Date(w.updated_at).toLocaleTimeString()}</span>
                  </div>
                </div>
              );
            })
          )}
        </div>

        {/* Workflow Detail Inspector */}
        <div className="space-y-4">
          <div className="p-5 rounded-2xl bg-[#0e1217] border border-white/[0.08] shadow-lg sticky top-24">
            <h2 className="text-xs font-semibold text-ink uppercase tracking-wider font-mono mb-4 flex items-center justify-between">
              <span>Pipeline Inspector</span>
              {selectedWorkflow && (
                <span className="text-accent font-mono">{selectedWorkflow.state}</span>
              )}
            </h2>

            {!selectedWorkflow ? (
              <div className="text-center py-12">
                <div className="w-10 h-10 mx-auto mb-2 text-xl text-muted">👈</div>
                <p className="text-xs text-muted">Select a workflow to inspect its execution graph and tasks.</p>
              </div>
            ) : (
              <WorkflowDetailView
                workflow={selectedWorkflow}
                onUpdate={async () => {
                  const fresh = await api.getWorkflow(selectedWorkflow.id);
                  setSelectedWorkflow(fresh);
                  mutate();
                }}
              />
            )}
          </div>
        </div>
      </div>
    </div>
  );
}

function WorkflowDetailView({
  workflow,
  onUpdate,
}: {
  workflow: Workflow;
  onUpdate: () => Promise<void>;
}) {
  const { data: tasks, mutate } = useSWR(`tasks-${workflow.id}`, () =>
    api.listTasks(workflow.id)
  );
  const [resuming, setResuming] = useState(false);

  async function handleResume() {
    setResuming(true);
    try {
      await api.resume(workflow.id);
      await onUpdate();
      await mutate();
    } catch (e) {
      alert((e as Error).message);
    } finally {
      setResuming(false);
    }
  }

  return (
    <div className="space-y-4 text-xs">
      <div>
        <div className="text-[10px] font-mono text-muted uppercase">Objective</div>
        <p className="text-sm font-semibold text-ink mt-0.5">{workflow.title}</p>
        <p className="text-muted mt-1 leading-relaxed">{workflow.objective}</p>
      </div>

      {workflow.state === "WAITING_APPROVAL" && (
        <div className="p-3 rounded-xl bg-warn/10 border border-warn/20 space-y-2">
          <p className="text-warn text-xs font-medium">
            ⚠️ This workflow paused for human approval. Once approved in the Approval Center, click resume:
          </p>
          <button
            onClick={handleResume}
            disabled={resuming}
            className="w-full py-2 rounded-lg bg-warn hover:bg-warn/90 text-black font-semibold text-xs transition-all"
          >
            {resuming ? "Resuming…" : "Resume Execution Pipeline"}
          </button>
        </div>
      )}

      {/* Tasks List */}
      <div>
        <div className="text-[10px] font-mono text-muted uppercase mb-2">
          Deconstructed Tasks ({tasks?.length ?? 0})
        </div>
        <div className="space-y-2">
          {(tasks ?? []).map((t) => (
            <div
              key={t.id}
              className="p-3 rounded-xl bg-black/40 border border-white/5 space-y-1"
            >
              <div className="flex items-center justify-between">
                <span className="font-semibold text-ink text-xs truncate">
                  {t.title}
                </span>
                <span
                  className={`px-1.5 py-0.2 rounded-full text-[9px] font-bold uppercase ${
                    t.state === "COMPLETED"
                      ? "bg-ok/10 text-ok"
                      : t.state === "FAILED"
                      ? "bg-bad/10 text-bad"
                      : "bg-white/5 text-muted"
                  }`}
                >
                  {t.state}
                </span>
              </div>
              <div className="text-[11px] text-accent font-mono">
                🤖 {t.agent_name}
              </div>
              {t.error && <p className="text-[11px] text-bad mt-1">{t.error}</p>}
            </div>
          ))}
        </div>
      </div>
    </div>
  );
}
