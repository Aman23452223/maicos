export type WorkflowState =
  | "PLANNED"
  | "RUNNING"
  | "WAITING_APPROVAL"
  | "WAITING_INPUT"
  | "COMPLETED"
  | "PARTIAL"
  | "FAILED"
  | "CANCELLED";

export interface Workflow {
  id: string;
  title: string;
  objective: string;
  state: WorkflowState;
  plan: { intent?: string; tasks: Array<{ agent: string; title: string }> };
  created_at: string;
  updated_at: string;
}

export interface WorkflowTask {
  id: string;
  agent_name: string;
  title: string;
  description: string;
  state: string;
  depends_on: string[];
  output: Record<string, unknown>;
  error: string | null;
}

export interface Approval {
  id: string;
  workflow_id: string;
  task_id: string | null;
  action: string;
  target_system: string;
  description: string;
  payload: Record<string, unknown>;
  status: "PENDING" | "APPROVED" | "REJECTED" | "EXPIRED";
  requested_by_agent: string;
  created_at: string;
}

export interface AgentInfo {
  id: string;
  name: string;
  description: string;
  capabilities: string[];
  allowed_tools: string[];
  enabled: boolean;
}

export interface ToolInfo {
  id: string;
  name: string;
  connector: string;
  operations: string[];
  enabled: boolean;
}

export interface ConversationSummary {
  id: string;
  title: string;
  created_at: string | null;
  workflow_count: number;
}

export interface DocumentInfo {
  id: string;
  name: string;
  mime_type: string;
  access_roles: string[];
  indexed: boolean;
}

export interface AuditEvent {
  id: number;
  actor: string;
  action: string;
  target_type: string;
  target_id: string;
  details: Record<string, unknown>;
  created_at: string;
}
