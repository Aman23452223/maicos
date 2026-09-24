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

async function requestForm<T>(path: string, form: FormData): Promise<T> {
  const auth = await getAuthHeader();
  const res = await fetch(`/api${path}`, {
    method: "POST",
    headers: { ...auth },
    body: form,
  });
  if (!res.ok) {
    const body = await res.text();
    throw new Error(`${res.status}: ${body}`);
  }
  return (await res.json()) as T;
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
  register: (email: string, password: string, name?: string, company_name?: string) =>
    request<{ access_token: string }>("/v1/auth/register", {
      method: "POST",
      body: JSON.stringify({ email, password, name, company_name }),
    }),
  me: () => request<{ id: string; email: string; name: string; roles: string[] }>("/v1/auth/me"),
  submitCommand: (objective: string, conversation_id?: string, plan_review = false) =>
    request<Workflow>("/v1/commands", {
      method: "POST",
      body: JSON.stringify({ objective, conversation_id, plan_review }),
    }),
  patchTask: (workflowId: string, taskId: string, patch: { title?: string; description?: string }) =>
    request<WorkflowTask>(`/v1/workflows/${workflowId}/tasks/${taskId}`, {
      method: "PATCH",
      body: JSON.stringify(patch),
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
  analyzeWebsite: (url: string, analysis_type = "my_business") =>
    request<{
      ok: boolean;
      profile: Record<string, unknown>;
      document_id: string;
      pages_crawled: number;
      analysis_id: string;
      version: number;
      updated: boolean;
      saved_to_knowledge: boolean;
    }>("/v1/intel/analyze-website", {
      method: "POST",
      body: JSON.stringify({ url, use_llm: false, analysis_type }),
    }),
  listIntelAnalyses: (analysis_type?: string) =>
    request<
      {
        id: string;
        type: string;
        url: string;
        company_name: string;
        version: number;
        status: string;
        last_analyzed_at: string | null;
        document_id: string | null;
      }[]
    >(`/v1/intel/analyses${analysis_type ? `?analysis_type=${analysis_type}` : ""}`),
  convertProspect: (analysis_id: string) =>
    request<{ ok: boolean; created: number; deduped: number }>(
      `/v1/intel/prospect/${analysis_id}/convert-lead`,
      { method: "POST" },
    ),
  getBusinessProfile: () => request<BusinessProfile>("/v1/business/profile"),
  updateBusinessProfile: (payload: Record<string, unknown>) =>
    request<{ ok: boolean }>("/v1/business/profile", {
      method: "PUT",
      body: JSON.stringify(payload),
    }),
  listGoals: () =>
    request<{ id: string; text: string; status: string }[]>("/v1/business/goals"),
  addGoal: (text: string) =>
    request<{ id: string; text: string; status: string }>("/v1/business/goals", {
      method: "POST",
      body: JSON.stringify({ text }),
    }),
  deleteGoal: (id: string) =>
    request<{ ok: boolean }>(`/v1/business/goals/${id}`, { method: "DELETE" }),
  capabilityGap: (intent: string) =>
    request<{
      intent: string;
      capabilities: { capability: string; status: string; detail: string }[];
      blockers: string[];
      ready: boolean;
      next_steps: string[];
    }>(`/v1/capabilities/gap?intent=${encodeURIComponent(intent)}`),
  replanWorkflow: (id: string) => request<Workflow>(`/v1/workflows/${id}/replan`, { method: "POST" }),
  insights: () =>
    request<{ type: string; insights: { kind: string; severity: string; message: string; action: string }[] }>(
      "/v1/insights",
    ),
  saveMemory: (kind: string, key: string, value: string) =>
    request<{ id: string }>("/v1/memory", {
      method: "POST",
      body: JSON.stringify({ kind, key, value }),
    }),
  listMemory: () =>
    request<{ id: string; kind: string; key: string; value: string }[]>("/v1/memory"),
  companyRun: (objective: string, plan_review = true) =>
    request<Workflow>("/v1/company/run", {
      method: "POST",
      body: JSON.stringify({ objective, plan_review }),
    }),
  companyCheckup: () =>
    request<{ signals_created: number; signals: { kind: string; severity: string; title: string; detail: string }[] }>(
      "/v1/company/checkup",
      { method: "POST" },
    ),
  companySignals: () =>
    request<{ id: string; kind: string; severity: string; title: string; detail: string; status: string }[]>(
      "/v1/company/signals",
    ),
  companyWorkforce: (intent: string) =>
    request<{ manager: string; team: { role: string; agent: string; capability: string; available: boolean }[]; missing_capabilities: string[] }>(
      `/v1/company/workforce?intent=${encodeURIComponent(intent)}`,
    ),
  companyBlueprint: (idea: string) =>
    request<{ idea: string; sections: Record<string, { status: string; text: string }>; notice: string }>(
      "/v1/company/blueprint",
      { method: "POST", body: JSON.stringify({ idea }) },
    ),
  companyUsage: () =>
    request<{ type: string; tasks: number; tool_calls: number; note: string }>("/v1/usage"),
  startupIdea: (idea: string) =>
    request<Record<string, unknown>>("/v1/startup/idea", {
      method: "POST",
      body: JSON.stringify({ idea }),
    }),
  startupValidate: (idea: string) =>
    request<{
      findings: string[]; sources: string[]; assumptions: string[];
      risks: string[]; opportunities: string[]; open_questions: string[];
      research_status: string;
    }>("/v1/startup/validate", { method: "POST", body: JSON.stringify({ idea }) }),
  startupBlueprintSave: (idea: string, sections: Record<string, unknown>) =>
    request<{ id: string; status: string }>("/v1/startup/blueprint", {
      method: "POST",
      body: JSON.stringify({ idea, sections }),
    }),
  startupBlueprints: () =>
    request<{ id: string; idea: string; status: string; sections: number }[]>(
      "/v1/startup/blueprints",
    ),
  startupBlueprintApprove: (id: string) =>
    request<{ id: string; status: string }>(`/v1/startup/blueprints/${id}/approve`, {
      method: "POST",
    }),
  startupBlueprintApply: (id: string) =>
    request<Record<string, unknown>>(`/v1/startup/blueprints/${id}/apply`, {
      method: "POST",
    }),
  startupCreateWorkspace: (name: string, blueprint_id?: string) =>
    request<{ id: string; name: string }>("/v1/startup/create-workspace", {
      method: "POST",
      body: JSON.stringify({ name, blueprint_id }),
    }),
  startupStatus: () =>
    request<{ stages: Record<string, { done: boolean; detail: string }>; readiness: number; done: number; total: number }>(
      "/v1/startup/status",
    ),
  startupRoles: () =>
    request<{ id: string; title: string; kind: string; status: string }[]>(
      "/v1/startup/roles",
    ),
  startupRoleAdd: (title: string, kind: string) =>
    request<{ id: string }>("/v1/startup/roles", {
      method: "POST",
      body: JSON.stringify({ title, kind }),
    }),
  discoverLeads: (query: string, provider = "search", limit = 20) =>
    request<{ status: string; message: string; prospects: Record<string, unknown>[] }>(
      "/v1/leads/discover",
      { method: "POST", body: JSON.stringify({ query, provider, limit }) },
    ),
  importLeads: (prospects: Record<string, unknown>[], auto_qualify = true) =>
    request<{ created: number; deduped: number; ids: string[] }>("/v1/leads/import", {
      method: "POST",
      body: JSON.stringify({ prospects, auto_qualify }),
    }),
  importCsv: (file: File, list_name = "") => {
    const form = new FormData();
    form.append("file", file);
    if (list_name) form.append("list_name", list_name);
    return requestForm<{ created: number; deduped: number; ids: string[]; source: string }>(
      "/v1/leads/import-csv",
      form,
    );
  },
  uploadDocument: (file: File) => {
    const form = new FormData();
    form.append("name", file.name);
    form.append("mime_type", file.type || "text/plain");
    form.append("file", file);
    return requestForm<{ id: string; name: string; indexed: boolean }>(
      "/v1/documents",
      form,
    );
  },
  listLeads: (status?: string) =>
    request<Lead[]>(`/v1/leads${status ? `?status=${status}` : ""}`),
  qualifyLead: (id: string) =>
    request<{ score: number; status: string }>(`/v1/leads/${id}/qualify`, {
      method: "POST",
    }),
  enrichLead: (id: string) =>
    request<{ ok: boolean }>(`/v1/leads/${id}/enrich`, { method: "POST" }),
  scheduleFollowups: (lead_id: string) =>
    request<{ ok: boolean; created: number }>(`/v1/followups/schedule`, {
      method: "POST",
      body: JSON.stringify({ lead_id }),
    }),
  runDueFollowups: () =>
    request<{ sent: number; skipped: number }>(`/v1/followups/run-due`, {
      method: "POST",
    }),
  funnel: () => request<Record<string, unknown>>("/v1/analytics/funnel"),
  weeklyReport: () => request<Record<string, unknown>>("/v1/reports/weekly"),
  integrationCatalog: () =>
    request<{
      workspace_id: string;
      integrations: {
        provider: string;
        name: string;
        description: string;
        auth_type: string;
        actions: string[];
        status: string;
        detail: string;
        account: string;
        note: string;
      }[];
    }>("/v1/integrations/catalog"),
  connectIntegration: (provider: string, account?: string) =>
    request<{ provider: string; status: string; detail?: string }>(
      `/v1/integrations/${provider}/connect`,
      { method: "POST", body: JSON.stringify(account ? { account } : {}) },
    ),
  disconnectIntegration: (provider: string) =>
    request<{ provider: string; status: string }>(
      `/v1/integrations/${provider}/disconnect`,
      { method: "POST" },
    ),
  configureIntegration: (provider: string, credentials: Record<string, string>) =>
    request<{ provider: string; saved: boolean; status: string; detail?: string }>(
      `/v1/integrations/${provider}/configure`,
      { method: "POST", body: JSON.stringify({ credentials }) },
    ),
  listWorkspaces: () =>
    request<{ id: string; name: string; role: string; status: string; current: boolean }[]>(
      "/v1/workspaces",
    ),
  team: () =>
    request<{ id: string; name: string; email: string; roles: string[] }[]>(
      "/v1/company/team",
    ),
  createStaffTask: (title: string, assignee_user_id?: string) =>
    request<{ id: string }>("/v1/company/tasks", {
      method: "POST",
      body: JSON.stringify({ title, assignee_user_id }),
    }),
  myTasks: () =>
    request<{ id: string; title: string; state: string; project_id: string; due_at: string | null }[]>(
      "/v1/company/tasks/mine",
    ),
  staffTaskState: (id: string, state: string) =>
    request<{ ok: boolean }>(`/v1/company/tasks/${id}/state`, {
      method: "POST",
      body: JSON.stringify({ state }),
    }),
  listOpps: () =>
    request<{ id: string; title: string; amount: number; stage: string; status: string; lead_id: string | null }[]>(
      "/v1/opportunities",
    ),
  patchOpp: (id: string, patch: { stage?: string; status?: string }) =>
    request<{ id: string; stage: string; status: string }>(`/v1/opportunities/${id}`, {
      method: "PATCH",
      body: JSON.stringify(patch),
    }),
  inbox: () =>
    request<{ lead_id: string | null; from: string; name: string; channel: string; messages: { body: string; classification: string; at: string | null }[] }[]>(
      "/v1/inbox",
    ),
  inboxReply: (lead_id: string | null, to: string, body: string) =>
    request<{ ok: boolean }>("/v1/inbox/reply", {
      method: "POST",
      body: JSON.stringify({ lead_id, to, body }),
    }),
  switchWorkspace: (workspace_id: string) =>
    request<{ access_token: string }>("/v1/auth/switch", {
      method: "POST",
      body: JSON.stringify({ workspace_id }),
    }),
  integrationStatus: () =>
    request<{
      workspace_id: string;
      capabilities: string[];
      providers: { provider: string; status: string; needs: string[]; configured: boolean }[];
    }>("/v1/integrations/status"),
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
  Lead,
  BusinessProfile,
} from "./types";
export type { Lead, BusinessProfile };
