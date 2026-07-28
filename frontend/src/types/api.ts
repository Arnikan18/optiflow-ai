// ─── Run Lifecycle ────────────────────────────────────────────────────────────

export type RunStatus =
  | 'RECEIVED'
  | 'RUNNING'
  | 'WAITING_FOR_CLARIFICATION'
  | 'WAITING_FOR_APPROVAL'
  | 'EXECUTING'
  | 'COMPLETED'
  | 'FAILED';

export interface RunSummary {
  run_id: string;
  status: RunStatus;
  current_node: string | null;
  recommended_plan_id: string | null;
  candidate_plans: CandidatePlan[];
}

// ─── SSE Event ────────────────────────────────────────────────────────────────

export interface RunEvent {
  event_id: string;
  run_id: string;
  sequence_number: number;
  event_type: string;
  source: string;
  summary: string | null;
  payload: Record<string, unknown> | null;
  state_version: number | null;
  // added client-side
  received_at?: string;
}

// ─── Candidate Plans ──────────────────────────────────────────────────────────

export interface PlanMetrics {
  match_rate: number;
  assigned_count: number;
  unassigned_count: number;
  arr_protected: number;
  [key: string]: number | string;
}

export interface PlanMetadata {
  solver_type: 'CP-SAT' | 'Greedy' | 'Greedy (Fallback)';
  solving_time_ms: number;
  solver_status: 'OPTIMAL' | 'FEASIBLE' | 'TIME_LIMIT';
  fallback_status: boolean;
  [key: string]: unknown;
}

export interface AllocationRecord {
  specialist_id: string;
  incident_id: string;
  customer_id?: string;
  [key: string]: unknown;
}

export interface CandidatePlan {
  plan_id: string;
  profile: string;
  description: string;
  objective_value: number;
  allocations: AllocationRecord[];
  unassigned_incidents: string[];
  metrics: PlanMetrics;
  metadata: PlanMetadata;
  explanation: string;
}

// ─── API Request/Response shapes ─────────────────────────────────────────────

export interface CreateRunResponse {
  run_id: string;
  status: 'RECEIVED';
}

export interface ApproveRunPayload {
  approval_status: 'APPROVED' | 'REJECTED' | 'MODIFY';
  recommended_plan?: CandidatePlan;
}

export interface ClarifyRunPayload {
  clarification_reply: string;
}

// ─── System Health ────────────────────────────────────────────────────────────

export type ServiceHealthStatus = 'online' | 'degraded' | 'offline' | 'checking';

export interface ServiceHealth {
  name: string;
  port: number;
  status: ServiceHealthStatus;
  latency_ms?: number;
}

// ─── Local persistence (localStorage) ────────────────────────────────────────

export interface RecentRun {
  run_id: string;
  goal_text: string;
  status: RunStatus;
  created_at: string;
}
