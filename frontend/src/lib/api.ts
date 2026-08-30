const TOKEN_KEY = "maicos.token";

export function getToken(): string | null {
  if (typeof window === "undefined") return null;
  return localStorage.getItem(TOKEN_KEY);
}

export function setToken(t: string | null) {
  if (typeof window === "undefined") return;
  if (t) localStorage.setItem(TOKEN_KEY, t);
  else localStorage.removeItem(TOKEN_KEY);
}

async function getAuthHeader(): Promise<Record<string, string>> {
  // Prefer Supabase session if present — it carries the same JWT the
  // backend will verify (RS256 against the project's JWKS).
  const { isSupabaseEnabled, getSupabase } = await import("./supabase");
  if (isSupabaseEnabled()) {
    const client = getSupabase();
    if (client) {
      const { data } = await client.auth.getSession();
      if (data.session?.access_token) {
        return { Authorization: `Bearer ${data.session.access_token}` };
      }
    }
  }
  const local = getToken();
  if (local) return { Authorization: `Bearer ${local}` };
  return {};
}

async function request<T>(path: string, init: RequestInit = {}): Promise<T> {
  const auth = await getAuthHeader();
  const res = await fetch(`/api${path}`, {
    ...init,
    headers: {
      "Content-Type": "application/json",
      ...auth,
      ...(init.headers || {}),
    },
  });
  if (!res.ok) {
    const body = await res.text();
    throw new Error(`${res.status}: ${body}`);
  }
  if (res.status === 204) return undefined as T;
  return (await res.json()) as T;
}

export const api = {
  login: (email: string, password: string) =>
    request<{ access_token: string }>("/v1/auth/login", {
      method: "POST",
      body: JSON.stringify({ email, password }),
    }),
  me: () => request<{ id: string; email: string; name: string; roles: string[] }>("/v1/auth/me"),
  submitCommand: (objective: string, conversation_id?: string) =>
    request<Workflow>("/v1/commands", {
      method: "POST",
      body: JSON.stringify({ objective, conversation_id }),
    }),
  listWorkflows: (state?: string) =>
    request<Workflow[]>(`/v1/workflows${state ? `?state=${state}` : ""}`),
  getWorkflow: (id: string) => request<Workflow>(`/v1/workflows/${id}`),
  listTasks: (id: string) => request<WorkflowTask[]>(`/v1/workflows/${id}/tasks`),
  resume: (id: string) =>
    request<Workflow>(`/v1/workflows/${id}/resume`, { method: "POST" }),
  listApprovals: (status?: string) =>
    request<Approval[]>(`/v1/approvals${status ? `?status=${status}` : ""}`),
  decide: (id: string, decision: "APPROVE" | "REJECT", note?: string) =>
    request<Approval>(`/v1/approvals/${id}/decision`, {
      method: "POST",
      body: JSON.stringify({ decision, note }),
    }),
  listAgents: () => request<AgentInfo[]>("/v1/agents"),
  listTools: () => request<ToolInfo[]>("/v1/tools"),
  setAgentEnabled: (id: string, enabled: boolean) =>
    request<AgentInfo>(`/v1/agents/${id}/enable?enabled=${enabled}`, {
      method: "POST",
    }),
  listAudit: () => request<AuditEvent[]>("/v1/audit"),
  listDocuments: () => request<DocumentInfo[]>("/v1/documents"),
  listConversations: () => request<ConversationSummary[]>("/v1/conversations"),
  scheduleWorkflow: (objective: string, runAt: string) =>
    request<{ job_id: string; run_at: string }>(
      `/v1/workflows/schedule?objective=${encodeURIComponent(objective)}&run_at=${encodeURIComponent(runAt)}`,
      { method: "POST" },
    ),
  getSettings: () =>
    request<{
      llm_provider: string;
      llm_default_model: string;
      openrouter_configured: boolean;
      openai_configured: boolean;
      anthropic_configured: boolean;
    }>("/v1/settings"),
  updateSettings: (payload: {
    llm_provider?: string;
    llm_default_model?: string;
    openrouter_api_key?: string;
    openai_api_key?: string;
    anthropic_api_key?: string;
  }) =>
    request<{
      llm_provider: string;
      llm_default_model: string;
      openrouter_configured: boolean;
      openai_configured: boolean;
      anthropic_configured: boolean;
    }>("/v1/settings", {
      method: "POST",
      body: JSON.stringify(payload),
    }),
};

import type {
  Workflow,
  WorkflowTask,
  Approval,
  AgentInfo,
  ToolInfo,
  AuditEvent,
  DocumentInfo,
  ConversationSummary,
} from "./types";
