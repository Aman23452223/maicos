"use client";

import { useEffect, useState } from "react";
import { api, getToken } from "@/lib/api";
import type { DocumentInfo } from "@/lib/types";

async function uploadRaw(
  name: string,
  mime: string,
  roles: string[],
  file?: File,
  text?: string,
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
  const [items, setItems] = useState<DocumentInfo[]>([]);
  const [name, setName] = useState("refund-policy.txt");
  const [text, setText] = useState(
    "Refunds are processed within 7 business days. Customers must request a refund via support.",
  );
  const [roles, setRoles] = useState("member,admin");
  const [file, setFile] = useState<File | null>(null);
  const [msg, setMsg] = useState<string | null>(null);

  async function refresh() {
    try {
      setItems(await api.listDocuments());
    } catch (e) {
      setMsg((e as Error).message);
    }
  }

  useEffect(() => {
    refresh();
  }, []);

  async function submit() {
    setMsg(null);
    try {
      const r = file
        ? await uploadRaw(name, file.type || "text/plain", roles.split(",").map((s) => s.trim()), file)
        : await uploadRaw(name, "text/plain", roles.split(",").map((s) => s.trim()), undefined, text);
      setMsg(`Indexed ${r.name}`);
      setFile(null);
      await refresh();
    } catch (e) {
      setMsg((e as Error).message);
    }
  }

  return (
    <div className="grid grid-cols-1 lg:grid-cols-3 gap-4">
      <div className="card p-4 lg:col-span-2">
        <div className="font-semibold mb-2">Index a document</div>
        <label className="text-xs text-muted">Name</label>
        <input className="input mb-2" value={name} onChange={(e) => setName(e.target.value)} />
        <label className="text-xs text-muted">Access roles (comma-separated)</label>
        <input className="input mb-2" value={roles} onChange={(e) => setRoles(e.target.value)} />
        <label className="text-xs text-muted">File (PDF / DOCX / TXT) — optional</label>
        <input
          className="input mb-2"
          type="file"
          onChange={(e) => setFile(e.target.files?.[0] || null)}
        />
        <label className="text-xs text-muted">…or paste text</label>
        <textarea
          className="input h-32"
          value={text}
          onChange={(e) => setText(e.target.value)}
          disabled={!!file}
        />
        <button className="btn mt-2" onClick={submit}>
          Index document
        </button>
        {msg && <div className="text-sm text-muted mt-2">{msg}</div>}
      </div>
      <div className="card p-4">
        <div className="font-semibold mb-2">Indexed</div>
        {items.length === 0 ? (
          <div className="text-muted text-sm">No documents yet.</div>
        ) : (
          <ul className="text-sm space-y-1">
            {items.map((d) => (
              <li key={d.id} className="flex justify-between gap-2">
                <span>{d.name}</span>
                <span className="text-xs text-muted">
                  {d.indexed ? "indexed" : "queued"}
                </span>
              </li>
            ))}
          </ul>
        )}
      </div>
    </div>
  );
}
