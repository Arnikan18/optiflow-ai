// Shared API envelope used by the demo endpoints.
export interface ApiEnvelope<T> {
  success: boolean;
  message: string;
  timestamp: string;
  data: T;
}

// Run lifecycle
export type RunStatus =
  | 'RECEIVED'
  | 'RUNNING'
  | 'WAITING_FOR_CLARIFICATION'
  | 'WAITING_FOR_APPROVAL'
  | 'EXECUTING'
  | 'REPLANNING'
  | 'EXECUTED'
  | 'FAILED_SAGA'
  | 'COMPLETED'
  | 'FAILED'
  | 'CANCELLED';

export interface ConfidenceReport {
  score: number;
  grade: 'HIGH' | 'MEDIUM' | 'LOW' | 'CRITICAL';
  freshness_penalty: number;
  completeness_penalty: number;
  conflict_penalty: number;
  total_penalty: number;
  freshness_age_hours: number;
  missing_field_count: number;
  conflict_count: number;
}

export interface AffectedCustomer {
  customer_id: string;
  tier: string;
  arr: number;
}

export interface AutonomyRiskReport {
  risk_level: 'HIGH' | 'STANDARD';
  reasons: string[];
  affected_customers: AffectedCustomer[];
  total_arr_exposure: number;
  allocation_count: number;
}

export interface SelectedTool {
  toolName: string;
  selected: boolean;
  reason: string;
  requestedEvidence: string[];
}

export interface ExcludedSpecialistIncident {
  specialist_id: string;
  incident_id: string;
}

export interface StructuredGoal {
  objective?: string;
  objectives?: string[];
  constraints?: string[];
  preferences?: string[];
  ambiguities?: string[];
  horizon?: string;
  [key: string]: unknown;
}

export interface CandidatePlanSummary {
  profile: string;
  objective_score: number;
  sla_score: number;
  revenue_score: number;
  fairness_score: number;
  workload_score: number;
  selected: boolean;
  recommendation_reason: string;
  rank: number;
}

export interface RunSummary {
  run_id: string;
  status: RunStatus;
  current_node: string | null;
  recommended_plan_id: string | null;
  candidate_plans: CandidatePlan[];
  confidence_report: ConfidenceReport | null;
  autonomy_risk_report: AutonomyRiskReport | null;
  replan_count: number;
  excluded_specialist_incidents: ExcludedSpecialistIncident[];
  structured_goal: StructuredGoal | null;
  selected_tools: SelectedTool[];
  business_summary: string | Record<string, unknown> | null;
  change_summary: string | Record<string, unknown> | null;
  candidate_plan_summary: CandidatePlanSummary[];
}

// SSE event
export interface RunEvent {
  event_id: string;
  run_id: string;
  sequence_number: number;
  event_type: string;
  source: string;
  summary: string | null;
  payload: Record<string, unknown> | null;
  state_version: number | null;
  received_at?: string;
}

// Candidate plans
export interface PlanMetrics {
  match_rate: number;
  assigned_count: number;
  unassigned_count: number;
  arr_protected: number;
  sla_breaches_avoided?: number;
  sla_score?: number;
  sla_risk_reduction?: number;
  fairness_score?: number;
  context_switching_count?: number;
  context_switching_score?: number;
  maximum_specialist_utilisation?: number;
  average_specialist_utilisation?: number;
  workload_distribution?: Record<string, number>;
  feasibility_status?: string;
  [key: string]: unknown;
}

export type SolverStatus =
  | 'OPTIMAL'
  | 'FEASIBLE'
  | 'TIME_LIMIT'
  | 'INFEASIBLE'
  | 'MODEL_INVALID'
  | 'UNKNOWN';

export interface PlanMetadata {
  solver_type: 'CP-SAT' | 'Greedy' | 'Greedy (Fallback)';
  solving_time_ms: number;
  solver_status: SolverStatus;
  fallback_status: boolean;
  feasibility?: boolean;
  duplicate_assignment_explanation?: string;
  [key: string]: unknown;
}

export interface AllocationRecord {
  specialist_id: string;
  incident_id: string;
  customer_id?: string;
  matched_skills?: string[];
  [key: string]: unknown;
}

export interface CandidatePlan {
  plan_id: string;
  profile_id?: string;
  profile_name?: string;
  profile: string;
  description: string;
  assignments: AllocationRecord[];
  allocations: AllocationRecord[];
  objective_weights?: Record<string, number>;
  objective_value: number;
  solver_status?: SolverStatus;
  feasible?: boolean;
  generated_at?: string;
  solve_time_ms?: number;
  failure_reason?: string | null;
  unassigned_incidents: string[];
  metrics: PlanMetrics;
  metadata: PlanMetadata;
  explanation: string;
}

// Run request and response payloads
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

// Demo portfolio
export type SourceStatusValue =
  | 'AVAILABLE'
  | 'UNAVAILABLE'
  | 'TIMEOUT'
  | 'INVALID_RESPONSE'
  | 'AUTH_FAILED';

export interface SourceStatusData {
  source_name: string;
  status: SourceStatusValue;
  freshness_timestamp: string | null;
  response_time_ms: number | null;
  error_code?: string | null;
  error_message?: string | null;
}

export interface DemoCustomer {
  customer_id: string;
  customer_name: string;
  segment: string | null;
  arr: number | null;
  business_value: number | null;
  renewal_date: string | null;
  renewal_risk: boolean | null;
  strategic_priority: string | null;
  current_incident_count: number;
}

export interface DemoIncident {
  incident_id: string;
  customer_id: string;
  title: string | null;
  summary: string | null;
  severity: string | null;
  status: string | null;
  sla_deadline: string | null;
  sla_risk: boolean | null;
  required_skills: string[];
  current_specialist_id: string | null;
  assignment_status: string | null;
  age_hours: number | null;
  opened_at: string | null;
}

export interface DemoSpecialist {
  specialist_id: string;
  specialist_name: string;
  skills: string[];
  availability: boolean | null;
  capacity: number | null;
  current_workload: number | null;
  reserved_workload: number | null;
  utilisation_percentage: number | null;
  active_assignments: number | null;
}

export interface DemoWorkload {
  specialist_id: string;
  assigned_count: number | null;
  tentative_reservation_count: number | null;
  confirmed_reservation_count: number | null;
  available_capacity: number | null;
  utilisation_percentage: number | null;
}

export interface PortfolioSummary {
  total_customers: number | null;
  total_active_incidents: number | null;
  total_at_risk_customers: number | null;
  total_arr_represented: number | null;
  total_arr_at_risk: number | null;
  total_specialists: number | null;
  available_specialists: number | null;
  average_workload: number | null;
  incidents_near_sla_breach: number | null;
  unassigned_incidents: number | null;
  generated_at: string;
  partial: boolean;
}

export interface DemoPortfolio {
  generated_at: string;
  degraded: boolean;
  customers: DemoCustomer[];
  incidents: DemoIncident[];
  specialists: DemoSpecialist[];
  workloads: DemoWorkload[];
  portfolio_summary: PortfolioSummary;
  sources: SourceStatusData[];
}

// Health
export type ComponentHealthStatus = 'HEALTHY' | 'DEGRADED' | 'UNHEALTHY';

export interface HealthComponent {
  name: string;
  status: ComponentHealthStatus;
  latency_ms: number | null;
  checked_at: string;
  message?: string | null;
}

export interface DemoHealth {
  overall_status: ComponentHealthStatus;
  checked_at: string;
  components: HealthComponent[];
}

export type ServiceHealthStatus = 'online' | 'degraded' | 'offline' | 'checking';

export interface ServiceHealth {
  name: string;
  port: number;
  status: ServiceHealthStatus;
  latency_ms?: number;
}

// Demo simulation
export type QueuedResponseStatus = 'ACCEPTED' | 'REJECTED';
export type FailureType = 'HTTP_ERROR' | 'TIMEOUT' | 'DELAY' | 'CONNECTION_FAILURE' | 'INVALID_RESPONSE';
export type FailureService = 'crm' | 'incident' | 'workforce' | 'communication';

export interface SpecialistResponseSimulationPayload {
  specialist_id?: string;
  incident_id?: string;
  status: QueuedResponseStatus;
  reason?: string;
  response_delay_seconds?: number;
  apply_once?: boolean;
  expires_after_seconds?: number;
}

export interface FailureSimulationPayload {
  service: FailureService;
  enabled?: boolean;
  failure_type?: FailureType;
  status_code?: number;
  delay_seconds?: number;
  affected_endpoint?: string;
  scope?: string;
  apply_once?: boolean;
  expires_after_seconds?: number;
  message?: string;
}

export interface SimulationState {
  communication: Record<string, unknown> | null;
  services: Record<string, unknown>;
  degraded: boolean;
  generated_at: string;
}

export interface DemoResetResult {
  degraded: boolean;
  services: Record<string, unknown>;
  reset_at: string;
}

// Execution verification
export type RecommendedExecutionState = 'COMPLETED' | 'WAITING' | 'COMPENSATE' | 'REPLAN' | 'FAILED';

export interface ComponentVerification {
  verified: boolean;
  result: string;
  failed_checks: string[];
  current_status?: string | null;
  assignment_status?: string | null;
  source_unavailable?: boolean;
  [key: string]: unknown;
}

export interface ExecutionVerification {
  run_id: string;
  overall_verified: boolean;
  workforce_verification: ComponentVerification;
  incident_verification: ComponentVerification;
  communication_verification: ComponentVerification;
  failed_components: string[];
  checked_at: string;
  recommended_next_state: RecommendedExecutionState;
  execution_receipt: Record<string, unknown>;
}

export interface ExecutionVerificationPayload {
  reservation_id: string;
  incident_id: string;
  specialist_id: string;
  assignment_request_id: string;
  plan_id?: string;
  profile_name?: string;
}

// Local persistence
export interface RecentRun {
  run_id: string;
  goal_text: string;
  status: RunStatus;
  created_at: string;
}
