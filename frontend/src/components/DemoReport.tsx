"use client";

import useSWR from "swr";
import { api } from "@/lib/api";
import { useAuth } from "@/contexts/AuthContext";
import type { Workflow, WorkflowTask } from "@/lib/types";

/** Demo Execution Report: one readable panel per command run.
 *
 * Assembled only from live data — workflow plan/tasks, the clients
 * report (persisted records), and integration status. Anything missing
 * renders as an explicit empty/blocked state, never invented.
 */
export function DemoReport({
  workflow,
  tasks,
}: {
  workflow: Workflow;
  tasks: WorkflowTask[];
}) {
  const { user } = useAuth();
  const { data: clients } = useSWR(user ? `demo-clients-${workflow.id}` : null, () =>
    api.clientsReport()
  );
  const { data: integrations } = useSWR(
    user ? `demo-integrations-${workflow.id}` : null,
    () => api.integrationStatus()
  );

  const rows = clients?.clients ?? [];
  const qualified = rows.filter((c) => c.status === "QUALIFIED");
  const review = clients?.review_candidates ?? [];
  const excluded = rows.filter((c) => c.quality_flag);
  const withFollowups = rows.filter((c) => c.followups_scheduled > 0);
  const totalScheduled = rows.reduce((n, c) => n + (c.followups_scheduled || 0), 0);

  const done = tasks.filter((t) => t.state === "COMPLETED").length;
  const failed = tasks.filter((t) => t.state === "FAILED");
  const waiting = tasks.filter((t) =>
    ["WAITING_APPROVAL", "WAITING_INPUT", "PENDING", "RUNNING"].includes(t.state)
  );
  const skipped = tasks.filter((t) => t.state === "SKIPPED");

  const providers = integrations?.providers ?? [];
  const working = providers.filter((p) => p.configured);
  const blocked = providers.filter((p) => !p.configured);

  return (
    <div
      id="demo-report"
      className="p-5 rounded-2xl bg-[#0e1217] border border-accent/25 shadow-[0_0_20px_rgba(91,141,239,0.12)] space-y-4"
    >
      <div className="flex items-center justify-between">
        <h3 className="text-sm font-semibold text-ink flex items-center gap-2">
          <span>🧾</span>
          <span>Demo Execution Report</span>
        </h3>
        <div className="flex items-center gap-2">
          <button
            onClick={() => window.print()}
            className="px-3 py-1.5 rounded-lg bg-white/5 hover:bg-white/10 border border-white/10 text-xs text-muted hover:text-ink transition-colors"
            title="Print this report for the presentation"
          >
            🖨️ Print
          </button>
          <span
            className={`px-2 py-0.5 rounded-full text-[10px] font-bold uppercase tracking-wider ${
              workflow.state === "COMPLETED"
                ? "bg-ok/10 text-ok border border-ok/20"
                : workflow.state === "FAILED"
                ? "bg-bad/10 text-bad border border-bad/20"
                : "bg-accent/10 text-accent border border-accent/20 animate-pulse"
            }`}
          >
            {workflow.state}
          </span>
        </div>
      </div>

      {/* 1. Command summary */}
      <section className="space-y-1">
        <SectionTitle n="1" label="Command summary" />
        <p className="text-xs text-ink/90 leading-relaxed">“{workflow.objective}”</p>
        <p className="text-[11px] text-muted">
          MAICOS understood intent:{" "}
          <span className="font-mono text-accent">{workflow.plan?.intent || "general"}</span>
        </p>
      </section>

      {/* 2. AI plan */}
      <section className="space-y-1.5">
        <SectionTitle n="2" label={`AI plan (${workflow.plan?.tasks?.length ?? tasks.length} steps)`} />
        <div className="space-y-1">
          {(workflow.plan?.tasks ?? []).map((s, i) => (
            <div key={i} className="text-[11px] text-muted">
              <span className="font-mono text-accent">{i + 1}. [{s.agent}]</span>{" "}
              <span className="text-ink/85">{s.title}</span>
            </div>
          ))}
          {(workflow.plan?.tasks ?? []).length === 0 && (
            <p className="text-[11px] text-muted">Plan steps listed in the task breakdown below.</p>
          )}
        </div>
      </section>

      {/* 3. Execution status */}
      <section className="space-y-1.5">
        <SectionTitle
          n="3"
          label={`Execution status (${done}/${tasks.length} completed)`}
        />
        <div className="space-y-1">
          {tasks.map((t) => (
            <div key={t.id} className="flex items-start gap-2 text-[11px]">
              <StateDot state={t.state} />
              <div className="min-w-0">
                <span className="text-ink/90 font-medium">{t.title}</span>{" "}
                <span className="text-muted font-mono">[{t.agent_name}]</span>
                {t.error && <div className="text-bad mt-0.5">{t.error}</div>}
              </div>
            </div>
          ))}
          {tasks.length === 0 && (
            <p className="text-[11px] text-muted">No task details loaded yet.</p>
          )}
        </div>
      </section>

      {/* 4. CRM results */}
      <section className="space-y-1.5">
        <SectionTitle n="4" label="CRM results (persisted records)" />
        {rows.length === 0 && (
          <p className="text-[11px] text-muted">No CRM records in this workspace yet.</p>
        )}
        {qualified.length > 0 && (
          <ResultGroup
            title={`Qualified (${qualified.length})`}
            tone="ok"
            items={qualified.map((c) => `${c.name} — score ${c.score} (${c.priority})`)}
          />
        )}
        {review.length > 0 && (
          <ResultGroup
            title={`Needs human review (${review.length}) — not qualified, needs a person`}
            tone="warn"
            items={review.map(
              (r) => `${r.name} — score ${r.score}, ${r.status}: ${r.reason.slice(0, 120)}`
            )}
          />
        )}
        {excluded.length > 0 && (
          <ResultGroup
            title={`Excluded as non-buyers (${excluded.length}) — kept in CRM, no outreach`}
            tone="muted"
            items={excluded.map(
              (c) => `${c.name} — ${c.quality_flag || "low-quality"}`
            )}
          />
        )}
        {rows.length > 0 && qualified.length === 0 && review.length === 0 && (
          <p className="text-[11px] text-muted">
            No qualified or reviewable leads right now — import or qualify records to proceed.
          </p>
        )}
      </section>

      {/* 5. Follow-ups */}
      <section className="space-y-1.5">
        <SectionTitle n="5" label="Follow-ups" />
        {withFollowups.length === 0 ? (
          <p className="text-[11px] text-muted">
            No follow-ups scheduled in this workspace. Eligible leads (QUALIFIED with a verified
            contact path) get sequences automatically; others list a reason in the task output.
          </p>
        ) : (
          <div className="space-y-1.5">
            {withFollowups.map((c) => (
              <div key={c.lead_id} className="text-[11px] leading-relaxed">
                <span className="font-medium text-ink">{c.name}</span>{" "}
                <span className="text-ok font-mono">
                  {c.followups_scheduled} scheduled
                </span>
                {c.next_due_at && (
                  <span className="text-muted">
                    {" "}· next due {new Date(c.next_due_at).toLocaleDateString()}
                  </span>
                )}
                <div className="text-muted font-mono break-all">
                  {(c.followups ?? []).slice(0, 3).map((f) => f.id.slice(0, 8)).join(" · ")}
                  {(c.followups ?? []).length > 3 &&
                    ` +${(c.followups ?? []).length - 3} more`}
                </div>
              </div>
            ))}
          </div>
        )}
      </section>

      {/* 6. Integration status */}
      <section className="space-y-1.5">
        <SectionTitle n="6" label="Integration status" />
        {providers.length === 0 ? (
          <p className="text-[11px] text-muted">Integration status unavailable.</p>
        ) : (
          <div className="flex flex-wrap gap-1.5">
            {working.map((p) => (
              <span
                key={p.provider}
                className="px-2 py-0.5 rounded-full text-[10px] font-mono bg-ok/10 text-ok border border-ok/20"
                title={(p.needs || []).join(", ")}
              >
                ✓ {p.provider}
              </span>
            ))}
            {blocked.map((p) => (
              <span
                key={p.provider}
                className="px-2 py-0.5 rounded-full text-[10px] font-mono bg-warn/10 text-warn border border-warn/20"
                title={`Needs: ${(p.needs || []).join(", ") || "credentials"}`}
              >
                ✕ {p.provider} — not configured
              </span>
            ))}
          </div>
        )}
        <p className="text-[10px] text-muted">
          Blocked integrations stay blocked — the demo never pretends they worked.
        </p>
      </section>

      {/* 7. Final report */}
      <section className="space-y-1">
        <SectionTitle n="7" label="Final report" />
        <p className="text-[11px] text-ink/85 leading-relaxed">
          {done} of {tasks.length} steps completed
          {skipped.length > 0 && `, ${skipped.length} skipped`}
          {failed.length > 0 && `, ${failed.length} failed`}
          {waiting.length > 0 && `, ${waiting.length} still pending/paused`}.
        </p>
        {failed.map((t) => (
          <p key={t.id} className="text-[11px] text-bad">
            ✕ {t.title}: {t.error || "failed — see task output"}
          </p>
        ))}
        {waiting
          .filter((t) => t.state === "WAITING_APPROVAL" || t.state === "WAITING_INPUT")
          .map((t) => (
            <p key={t.id} className="text-[11px] text-warn">
              ⏸ {t.title}: paused for human input/approval — open Approvals to continue.
            </p>
          ))}
        {failed.length === 0 && waiting.length === 0 && (
          <p className="text-[11px] text-ok">✓ Nothing failed, nothing waiting — run is complete.</p>
        )}
      </section>
    </div>
  );
}

function SectionTitle({ n, label }: { n: string; label: string }) {
  return (
    <div className="text-[10px] font-mono text-muted uppercase">
      <span className="text-accent font-bold">{n}.</span> {label}
    </div>
  );
}

function StateDot({ state }: { state: string }) {
  const color =
    state === "COMPLETED"
      ? "bg-ok"
      : state === "FAILED"
      ? "bg-bad"
      : state === "SKIPPED"
      ? "bg-white/30"
      : "bg-warn animate-pulse";
  return <span className={`mt-1 w-2 h-2 rounded-full shrink-0 ${color}`} title={state} />;
}

function ResultGroup({
  title,
  tone,
  items,
}: {
  title: string;
  tone: "ok" | "warn" | "muted";
  items: string[];
}) {
  const border =
    tone === "ok"
      ? "border-ok/20"
      : tone === "warn"
      ? "border-warn/20"
      : "border-white/10";
  return (
    <div className={`p-2 rounded-lg bg-white/[0.02] border ${border}`}>
      <div className="text-[11px] font-semibold text-ink mb-1">{title}</div>
      <div className="space-y-0.5">
        {items.slice(0, 8).map((s, i) => (
          <div key={i} className="text-[11px] text-muted">
            • {s}
          </div>
        ))}
        {items.length > 8 && (
          <div className="text-[10px] text-muted font-mono">+{items.length - 8} more</div>
        )}
      </div>
    </div>
  );
}
