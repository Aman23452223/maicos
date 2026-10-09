"use client";

/** Shared renderer for a workflow task's real saved output.
 *
 * Renders ONLY what the API returned in `task.output` — never invented.
 * Email drafts get a dedicated To/Subject/Body view; everything else
 * falls back to an honest scalar/list/JSON rendering.
 */

export function hasSavedOutput(output: unknown): boolean {
  return !!output && typeof output === "object" && Object.keys(output).length > 0;
}

function asRecord(v: unknown): Record<string, unknown> | null {
  return v && typeof v === "object" && !Array.isArray(v)
    ? (v as Record<string, unknown>)
    : null;
}

/** One-line preview shown without expanding (e.g. email subject). */
export function taskOutputPreview(output: Record<string, unknown>): string | null {
  const draft = asRecord(output.draft);
  if (draft) {
    const subject = draft.subject != null ? String(draft.subject) : "";
    const to = draft.to != null ? String(draft.to) : "";
    if (subject || to) return `✉️ ${subject}${to ? ` → ${to}` : ""}`.trim();
    return "✉️ Email draft saved";
  }
  const keys = Object.keys(output);
  if (keys.length === 0) return null;
  // Prefer a short human scalar if one exists.
  for (const k of ["summary", "brief", "message", "result", "count"]) {
    const v = output[k];
    if (typeof v === "string" && v.trim()) return v.trim().slice(0, 120);
    if (typeof v === "number") return `${k}: ${v}`;
  }
  return `${keys.length} field${keys.length === 1 ? "" : "s"} saved`;
}

/** Render a task's real saved output — only what the API returned. */
export function TaskOutputView({ output }: { output: Record<string, unknown> }) {
  const draft = asRecord(output.draft);
  return (
    <div className="mt-2 pt-2 border-t border-white/[0.07] space-y-2">
      <div className="text-[10px] font-mono text-muted uppercase">
        Saved output
      </div>
      {draft && (
        <div className="p-2.5 rounded-lg bg-white/[0.03] border border-white/[0.07] space-y-1.5">
          <div className="flex items-center justify-between">
            <span className="text-[11px] font-semibold text-ink">✉️ Email draft</span>
            <span className="px-1.5 py-0.2 rounded-full text-[9px] font-bold uppercase bg-warn/10 text-warn border border-warn/20">
              {String(draft.status ?? "DRAFT")} — not sent
            </span>
          </div>
          {draft.to != null && (
            <div className="text-[11px]">
              <span className="text-muted font-mono">To: </span>
              <span className="text-ink">{String(draft.to)}</span>
            </div>
          )}
          {draft.subject != null && (
            <div className="text-[11px]">
              <span className="text-muted font-mono">Subject: </span>
              <span className="text-ink font-medium">{String(draft.subject)}</span>
            </div>
          )}
          {draft.body != null && (
            <div className="text-[11px] text-ink/90 whitespace-pre-wrap leading-relaxed max-h-48 overflow-y-auto">
              {String(draft.body)}
            </div>
          )}
        </div>
      )}
      <GenericOutputView output={output} skipKeys={draft ? ["draft"] : []} />
    </div>
  );
}

/** Fallback renderer: scalars as rows, arrays summarized, nothing invented. */
function GenericOutputView({
  output,
  skipKeys,
}: {
  output: Record<string, unknown>;
  skipKeys: string[];
}) {
  const entries = Object.entries(output).filter(([k]) => !skipKeys.includes(k));
  if (entries.length === 0) return null;
  return (
    <div className="space-y-1">
      {entries.slice(0, 10).map(([k, v]) => (
        <div key={k} className="text-[11px] leading-relaxed">
          <span className="text-muted font-mono">{k}: </span>
          <OutputValue value={v} />
        </div>
      ))}
      {entries.length > 10 && (
        <div className="text-[10px] text-muted font-mono">
          +{entries.length - 10} more fields
        </div>
      )}
    </div>
  );
}

function OutputValue({ value }: { value: unknown }) {
  if (value == null) return <span className="text-muted">—</span>;
  if (typeof value === "string" || typeof value === "number" || typeof value === "boolean") {
    const s = String(value);
    return (
      <span className="text-ink break-words">
        {s.length > 300 ? `${s.slice(0, 300)}…` : s}
      </span>
    );
  }
  if (Array.isArray(value)) {
    if (value.length === 0) return <span className="text-muted">[]</span>;
    return (
      <span className="text-ink">
        [{value.length} item{value.length === 1 ? "" : "s"}]{" "}
        <span className="text-muted">
          {value
            .slice(0, 3)
            .map((x) =>
              typeof x === "object" && x !== null
                ? JSON.stringify(x).slice(0, 80)
                : String(x).slice(0, 80)
            )
            .join(" · ")}
        </span>
      </span>
    );
  }
  if (typeof value === "object") {
    const s = JSON.stringify(value);
    return (
      <span className="text-ink/90 font-mono break-words">
        {s.length > 300 ? `${s.slice(0, 300)}…` : s}
      </span>
    );
  }
  return null;
}
