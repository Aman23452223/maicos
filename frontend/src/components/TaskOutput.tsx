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
  for (const [key, icon] of [["draft", "✉️"], ["sent", "📤"]] as const) {
    const rec = asRecord(output[key]);
    if (rec) {
      const subject = rec.subject != null ? String(rec.subject) : "";
      const to = rec.to != null ? String(rec.to) : "";
      if (subject || to) return `${icon} ${subject}${to ? ` → ${to}` : ""}`.trim();
      return `${icon} Email ${key} saved`;
    }
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
  const sent = asRecord(output.sent);
  const skip = [...(draft ? ["draft"] : []), ...(sent ? ["sent"] : [])];
  return (
    <div className="mt-2 pt-2 border-t border-white/[0.07] space-y-2">
      <div className="text-[10px] font-mono text-muted uppercase">
        Saved output
      </div>
      {draft && <MessageRecordView label="Email draft" record={draft} sent={false} />}
      {sent && <MessageRecordView label="Email sent" record={sent} sent={true} />}
      <GenericOutputView output={output} skipKeys={skip} />
    </div>
  );
}

/** To/Subject/Body view for a persisted email record (draft or sent). */
function MessageRecordView({
  label,
  record,
  sent,
}: {
  label: string;
  record: Record<string, unknown>;
  sent: boolean;
}) {
  return (
    <div className="p-2.5 rounded-lg bg-white/[0.03] border border-white/[0.07] space-y-1.5">
      <div className="flex items-center justify-between">
        <span className="text-[11px] font-semibold text-ink">✉️ {label}</span>
        <span
          className={`px-1.5 py-0.2 rounded-full text-[9px] font-bold uppercase border ${
            sent
              ? "bg-ok/10 text-ok border-ok/20"
              : "bg-warn/10 text-warn border-warn/20"
          }`}
        >
          {String(record.status ?? (sent ? "SENT" : "DRAFT"))}
          {sent ? "" : " — not sent"}
        </span>
      </div>
      {record.to != null && (
        <div className="text-[11px]">
          <span className="text-muted font-mono">To: </span>
          <span className="text-ink">{String(record.to)}</span>
        </div>
      )}
      {record.subject != null && (
        <div className="text-[11px]">
          <span className="text-muted font-mono">Subject: </span>
          <span className="text-ink font-medium">{String(record.subject)}</span>
        </div>
      )}
      {record.body != null && (
        <div className="text-[11px] text-ink/90 whitespace-pre-wrap leading-relaxed max-h-48 overflow-y-auto">
          {String(record.body)}
        </div>
      )}
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
