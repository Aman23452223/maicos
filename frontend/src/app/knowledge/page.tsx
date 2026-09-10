"use client";

import { useEffect, useState, useCallback } from "react";
import { api, getToken } from "@/lib/api";
import { useAuth } from "@/contexts/AuthContext";
import type { DocumentInfo } from "@/lib/types";

async function uploadDocument(
  name: string,
  mime: string,
  roles: string[],
  file?: File,
  text?: string
): Promise<DocumentInfo> {
  const fd = new FormData();
  fd.append("name", name);
  fd.append("mime_type", mime);
  fd.append("access_roles", roles.join(","));
  if (file) fd.append("file", file);
  if (text) fd.append("text", text);

  const token = getToken();
  const res = await fetch("/api/v1/documents", {
    method: "POST",
    headers: token ? { Authorization: `Bearer ${token}` } : {},
    body: fd,
  });
  if (!res.ok) throw new Error(`${res.status}: ${await res.text()}`);
  return (await res.json()) as DocumentInfo;
}

export default function KnowledgePage() {
  const { user, openAuthModal } = useAuth();
  const [items, setItems] = useState<DocumentInfo[]>([]);
  const [name, setName] = useState("refund-policy.txt");
  const [text, setText] = useState(
    "Refunds are processed within 7 business days. Customers must request a refund via support."
  );
  const [roles, setRoles] = useState("member,admin");
  const [file, setFile] = useState<File | null>(null);
  const [loading, setLoading] = useState(false);
  const [msg, setMsg] = useState<string | null>(null);
  const [err, setErr] = useState<string | null>(null);

  const refresh = useCallback(async () => {
    if (!user) return;
    try {
      setItems(await api.listDocuments());
    } catch (e) {
      setErr((e as Error).message);
    }
  }, [user]);

  useEffect(() => {
    if (user) refresh();
  }, [user, refresh]);

  async function handleIndex(e: React.FormEvent) {
    e.preventDefault();
    setMsg(null);
    setErr(null);
    setLoading(true);

    try {
      const docName = file ? file.name : name;
      const mime = file ? file.type || "text/plain" : "text/plain";
      const roleList = roles.split(",").map((s) => s.trim()).filter(Boolean);

      const r = file
        ? await uploadDocument(docName, mime, roleList, file)
        : await uploadDocument(docName, mime, roleList, undefined, text);

      setMsg(`Document "${r.name}" successfully indexed into the Knowledge Vault.`);
      setFile(null);
      await refresh();
    } catch (e) {
      setErr((e as Error).message);
    } finally {
      setLoading(false);
    }
  }

  if (!user) {
    return (
      <div className="max-w-2xl mx-auto py-12 px-4 text-center">
        <div className="w-16 h-16 mx-auto mb-6 rounded-2xl bg-gradient-to-tr from-accent/20 to-purple-500/20 border border-accent/30 flex items-center justify-center text-2xl shadow-[0_0_30px_rgba(91,141,239,0.2)]">
          📚
        </div>
        <h1 className="text-2xl font-bold tracking-tight text-ink mb-2">
          Company Knowledge Vault
        </h1>
        <p className="text-sm text-muted max-w-md mx-auto mb-8">
          Upload internal SOPs, pricing sheets, compliance rules, and product specs for semantic RAG search across your AI workforce.
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
      {/* Header */}
      <div>
        <h1 className="text-xl font-bold tracking-tight text-ink flex items-center gap-2">
          <span>📚</span>
          <span>Knowledge Vault & RAG Index</span>
        </h1>
        <p className="text-xs text-muted mt-0.5">
          Train autonomous agents on your company's proprietary policies, wikis, and documents.
        </p>
      </div>

      <div className="grid grid-cols-1 lg:grid-cols-3 gap-6">
        {/* Upload Deck */}
        <div className="lg:col-span-2 p-6 rounded-2xl bg-[#0e1217] border border-white/[0.08] shadow-lg">
          <h2 className="text-sm font-semibold text-ink mb-4 flex items-center gap-2">
            <span>📄</span>
            <span>Index New Document</span>
          </h2>

          <form onSubmit={handleIndex} className="space-y-4">
            <div>
              <label className="block text-xs font-medium text-muted mb-1">
                Document Name / Title
              </label>
              <input
                className="w-full bg-black/40 border border-white/10 rounded-lg px-3 py-2 text-xs text-ink focus:outline-none focus:border-accent"
                value={name}
                onChange={(e) => setName(e.target.value)}
                placeholder="e.g. enterprise-refund-policy.pdf"
                required
              />
            </div>

            <div>
              <label className="block text-xs font-medium text-muted mb-1">
                Authorized Access Roles (comma-separated)
              </label>
              <input
                className="w-full bg-black/40 border border-white/10 rounded-lg px-3 py-2 text-xs text-ink focus:outline-none focus:border-accent font-mono"
                value={roles}
                onChange={(e) => setRoles(e.target.value)}
                placeholder="admin, member, finance"
              />
            </div>

            <div>
              <label className="block text-xs font-medium text-muted mb-1">
                Upload File (PDF / DOCX / TXT)
              </label>
              <input
                type="file"
                onChange={(e) => setFile(e.target.files?.[0] || null)}
                className="w-full text-xs text-muted file:mr-3 file:py-1.5 file:px-3 file:rounded-lg file:border-0 file:text-xs file:font-medium file:bg-white/10 file:text-ink hover:file:bg-white/15 cursor-pointer"
              />
            </div>

            <div>
              <label className="block text-xs font-medium text-muted mb-1">
                …or Paste Raw Content
              </label>
              <textarea
                className="w-full h-28 bg-black/40 border border-white/10 rounded-lg p-3 text-xs text-ink focus:outline-none focus:border-accent font-mono resize-none"
                value={text}
                onChange={(e) => setText(e.target.value)}
                disabled={!!file}
                placeholder="Paste company instructions or context for agents…"
              />
            </div>

            {msg && (
              <div className="p-3 rounded-lg bg-ok/10 border border-ok/30 text-ok text-xs">
                ✓ {msg}
              </div>
            )}

            {err && (
              <div className="p-3 rounded-lg bg-bad/10 border border-bad/30 text-bad text-xs">
                {err}
              </div>
            )}

            <button
              type="submit"
              disabled={loading}
              className="px-5 py-2.5 rounded-xl bg-accent hover:bg-accent/90 text-bg font-semibold text-xs transition-all shadow-[0_0_15px_rgba(91,141,239,0.3)] disabled:opacity-50 flex items-center gap-2"
            >
              {loading ? "Indexing into Vector DB…" : "⚡ Index into Knowledge Vault"}
            </button>
          </form>
        </div>

        {/* Indexed Documents List */}
        <div className="p-5 rounded-2xl bg-[#0e1217] border border-white/[0.08] shadow-lg">
          <div className="flex items-center justify-between mb-4">
            <h3 className="text-xs font-semibold text-ink uppercase tracking-wider font-mono">
              Indexed Documents ({items.length})
            </h3>
            <button
              onClick={refresh}
              className="text-xs text-muted hover:text-ink transition-colors"
            >
              Refresh
            </button>
          </div>

          {items.length === 0 ? (
            <div className="text-center py-12 text-muted text-xs">
              No documents indexed yet.
            </div>
          ) : (
            <div className="space-y-2">
              {items.map((d) => (
                <div
                  key={d.id}
                  className="p-3 rounded-xl bg-black/30 border border-white/5 flex items-center justify-between gap-3 text-xs"
                >
                  <div className="min-w-0">
                    <div className="font-medium text-ink truncate">{d.name}</div>
                    <div className="text-[10px] text-muted font-mono">
                      Roles: {d.access_roles?.join(", ") || "all"}
                    </div>
                  </div>
                  <span
                    className={`px-2 py-0.5 rounded-full text-[9px] font-bold uppercase tracking-wider flex-shrink-0 ${
                      d.indexed
                        ? "bg-ok/10 text-ok border border-ok/20"
                        : "bg-warn/10 text-warn border border-warn/20"
                    }`}
                  >
                    {d.indexed ? "Ready" : "Queued"}
                  </span>
                </div>
              ))}
            </div>
          )}
        </div>
      </div>
    </div>
  );
}
