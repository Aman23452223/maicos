"use client";

import useSWR from "swr";
import { useState } from "react";
import { api } from "@/lib/api";
import { useRealtime } from "@/lib/realtime";
import { statePillClass } from "@/lib/ui";
import type { Workflow, WorkflowState } from "@/lib/types";

const STATE_FILTERS: { label: string; value: WorkflowState | "" }[] = [
  { label: "All", value: "" },
  { label: "Running", value: "RUNNING" },
  { label: "Waiting", value: "WAITING_APPROVAL" },
  { label: "Completed", value: "COMPLETED" },
  { label: "Partial", value: "PARTIAL" },
  { label: "Failed", value: "FAILED" },
];

export default function WorkflowsPage() {
  const [filter, setFilter] = useState<WorkflowState | "">("");
  const key = `workflows-${filter || "all"}`;
  const { data, error, mutate } = useSWR<Workflow[]>(key, () =>
    api.listWorkflows(filter || undefined),
  );
  // Live updates from Supabase Realtime when enabled. Falls back to
  // SWR polling when the channel is unavailable.
  const realtime = useRealtime<Workflow>("workflows");
  const liveWorkflows =
    realtime.status === "ready" && realtime.data.length > 0
      ? realtime.data
      : (data ?? []);
  const [open, setOpen] = useState<Workflow | null>(null);

  return (
    <div className="grid grid-cols-1 lg:grid-cols-3 gap-4">
      <div className="card p-4 lg:col-span-2">
        <div className="flex items-center justify-between mb-2">
          <div className="font-semibold">Workflows</div>
          <div className="flex gap-1">
            {STATE_FILTERS.map((f) => (
              <button
                key={f.value || "all"}
                onClick={() => setFilter(f.value)}
                className={`px-2 py-1 text-xs rounded ${
                  filter === f.value
                    ? "bg-accent text-white"
                    : "bg-panel text-muted"
                }`}
              >
                {f.label}
              </button>
            ))}
          </div>
        </div>
        {error && <div className="text-bad text-sm">{String(error)}</div>}
        <table className="w-full text-sm">
          <thead className="text-muted text-left">
            <tr>
              <th className="py-2">Title</th>
              <th>State</th>
              <th>Updated</th>
            </tr>
          </thead>
          <tbody>
            {(filter
              ? liveWorkflows.filter((w) => w.state === filter)
              : liveWorkflows
            ).map((w) => (
              <tr
                key={w.id}
                className="border-t border-line cursor-pointer hover:bg-line/30"
                onClick={() => setOpen(w)}
              >
                <td className="py-2">{w.title}</td>
                <td>
                  <span className={statePillClass(w.state)}>{w.state}</span>
                </td>
                <td className="text-muted text-xs">
                  {new Date(w.updated_at).toLocaleString()}
                </td>
              </tr>
            ))}
            {liveWorkflows.length === 0 && (
              <tr>
                <td colSpan={3} className="text-muted text-sm py-4">
                  No workflows yet. Submit one from the AI Command Center.
                </td>
              </tr>
            )}
          </tbody>
        </table>
      </div>

      <div className="card p-4">
        <div className="font-semibold mb-2">Detail</div>
        {!open ? (
          <div className="text-muted text-sm">Select a workflow to view.</div>
        ) : (
          <WorkflowDetail workflow={open} onResume={async () => {
            await api.resume(open.id);
            const fresh = await api.getWorkflow(open.id);
            setOpen(fresh);
          }} />
        )}
      </div>
    </div>
  );
}

function WorkflowDetail({
  workflow,
  onResume,
}: {
  workflow: Workflow;
  onResume: () => Promise<void>;
}) {
  const tasks = useSWR(`tasks-${workflow.id}`, () => api.listTasks(workflow.id));
  return (
    <div>
      <div className="text-xs text-muted font-mono break-all">{workflow.id}</div>
      <div className="mt-1 font-semibold">{workflow.title}</div>
      <div className="text-sm text-muted">{workflow.objective}</div>
      <div className="mt-2 flex items-center gap-2">
        <span className={statePillClass(workflow.state)}>{workflow.state}</span>
        {workflow.state === "WAITING_APPROVAL" && (
          <button className="btn-ghost text-xs" onClick={onResume}>
            Resume
          </button>
        )}
      </div>
      <div className="mt-3">
        <div className="text-sm font-semibold mb-1">Tasks</div>
        <ul className="text-sm space-y-1">
          {(tasks.data ?? []).map((t) => (
            <li key={t.id} className="flex justify-between gap-2">
              <span>
                {t.agent_name} · {t.title}
              </span>
              <span className={statePillClass(t.state)}>{t.state}</span>
            </li>
          ))}
        </ul>
      </div>
    </div>
  );
}
