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

export type PreferenceLearningState = 'COLD_START' | 'LEARNING' | 'MATURE';
export type PreferenceConfidenceLevel = 'LOW' | 'MEDIUM' | 'HIGH';

export interface PersonalizedRecommendation {
  candidate_plan_id: string;
  candidate_index: number;
  preference_score: number;
  confidence: number;
  confidence_level: PreferenceConfidenceLevel;
  learning_state: PreferenceLearningState;
  reason: string;
  profile?: string | null;
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
  personalized_recommendation: PersonalizedRecommendation | null;
  candidate_plan_summary: CandidatePlanSummary[];
}

export interface PreferenceRecommendationStatistics {
  shown: number;
  accepted: number;
  rejected: number;
  acceptance_rate: number;
  last_updated: string | null;
  last_recommendation_timestamp: string | null;
}

export interface RecentPreferenceDecision {
  event_id: string;
  run_id: string;
  decision: string;
  selected_profile: string | null;
  personalized_profile: string | null;
  accepted_personalized: boolean | null;
  decision_reason: string | null;
  decision_source: string | null;
  goal_text: string | null;
  created_at: string;
}

export interface PreferenceSummary {
  learning_state: PreferenceLearningState;
  total_decisions: number;
  runs_until_next_state: number;
  cold_start_runs_required: number;
  mature_runs_required: number;
  profile_counts: Record<string, number>;
  dominant_profile: string | null;
  dominant_profile_share: number;
  confidence: number;
  recommendation_statistics: PreferenceRecommendationStatistics;
  learned_constraints: string[];
  recent_decisions: RecentPreferenceDecision[];
  updated_at: string;
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
  decision_reason?: string;
  decision_source?: 'AI_RECOMMENDATION' | 'ALTERNATIVE_PLAN' | 'MODIFICATION' | 'MANUAL_PLAN' | 'REJECT_ALL';
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

export interface PrioritySignal {
  key: string;
  label: string;
  points: number;
}

export interface DemoIncident {
  incident_id: string;
  customer_id: string;
  customer_name: string | null;
  title: string | null;
  summary: string | null;
  severity: string | null;
  status: string | null;
  sla_deadline: string | null;
  sla_risk: boolean | null;
  minutes_to_sla: number | null;
  estimated_effort_minutes: number | null;
  required_skills: string[];
  arr_exposure: number | null;
  strategic_priority: string | null;
  priority_rank: number | null;
  priority_score: number | null;
  priority_signals: PrioritySignal[];
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
  available_capacity: number | null;
  operationally_available: boolean | null;
  completed_assignments_30d: number;
  sla_success_rate_30d: number | null;
  average_resolution_minutes_30d: number | null;
  assignment_acceptance_rate_30d: number | null;
  capacity_reliability_rate_30d: number | null;
  effectiveness_score: number | null;
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

// Dynamic enterprise simulation
export type EnterpriseSimulationMode = 'TIMELINE' | 'INTERACTIVE';
export type EnterpriseSimulationStatus =
  | 'IDLE'
  | 'RUNNING'
  | 'PAUSED'
  | 'STOPPED'
  | 'COMPLETED'
  | 'ERROR';
export type EnterpriseEventType =
  | 'NEW_TICKET'
  | 'RESOLVE_TICKET'
  | 'ESCALATE_PRIORITY'
  | 'CHANGE_SLA'
  | 'CHANGE_ESTIMATED_EFFORT'
  | 'CHANGE_WORKER_CAPACITY'
  | 'ENGINEER_ON_LEAVE'
  | 'ENGINEER_RETURNED';
export type EnterpriseEventProcessingStatus =
  | 'RECEIVED'
  | 'VALIDATED'
  | 'APPLIED'
  | 'NOTIFIED'
  | 'FAILED'
  | 'PARTIALLY_APPLIED';
export type EnterpriseNotificationStatus =
  | 'NOT_REQUIRED'
  | 'PENDING'
  | 'DELIVERED'
  | 'FAILED'
  | 'ACKNOWLEDGED';

export interface EnterpriseScenario {
  scenario_id: string;
  name: string;
  description: string;
  version: string;
  mode: EnterpriseSimulationMode;
  duration: string;
  start_time: string;
  end_time: string;
  timezone: string;
  stages: string[];
  tags: string[];
  schema_version: string;
  created_at: string;
}

export interface EnterpriseScenarioList {
  scenarios: EnterpriseScenario[];
  default_scenario_id: string | null;
}

export interface EnterpriseSimulationStatusData {
  simulation_id: string | null;
  scenario_id: string | null;
  scenario_name: string | null;
  mode: EnterpriseSimulationMode | null;
  status: EnterpriseSimulationStatus;
  current_time: string | null;
  current_stage: string | null;
  current_timeline_position: number;
  processed_events: string[];
  pending_events: string[];
  last_event: Record<string, unknown> | null;
  enterprise_changed: boolean;
  notification_status: EnterpriseNotificationStatus;
  started_at: string | null;
  paused_at: string | null;
  completed_at: string | null;
  updated_at: string | null;
}

export interface StartEnterpriseSimulationPayload {
  scenario_id?: string;
  mode: EnterpriseSimulationMode;
  reset_existing?: boolean;
  auto_advance?: boolean;
}

export interface StartEnterpriseSimulationResult extends EnterpriseSimulationStatusData {
  next_event: Record<string, unknown> | null;
}

export interface AdvanceEnterpriseSimulationResult extends EnterpriseSimulationStatusData {
  processed_event: Record<string, unknown> | null;
  next_event: Record<string, unknown> | null;
  completed: boolean;
}

export interface JudgeEnterpriseEventPayload {
  event_type: EnterpriseEventType;
  payload: Record<string, unknown>;
  event_id?: string;
  scenario_id?: string;
  description?: string;
  effective_time?: string;
  idempotency_key?: string;
}

export interface EnterpriseEventResult {
  accepted: boolean;
  event_id: string;
  event_type: EnterpriseEventType;
  processing_status: EnterpriseEventProcessingStatus;
  enterprise_changed: boolean;
  applied_at: string | null;
  notification_status: EnterpriseNotificationStatus;
  notification_id: string | null;
  changed_entities: Array<Record<string, unknown>>;
  errors: Array<Record<string, unknown>>;
}

export interface EnterpriseEventHistory {
  events: Array<Record<string, unknown>>;
  page: number;
  page_size: number;
  total_items: number;
  total_pages: number;
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

// Secure LLM settings
export type LLMProviderName = 'gemini' | 'groq';
export type LLMEngineMode = 'rules_only' | 'ai_assisted';

export interface LLMCredentialInput {
  label: string;
  api_key: string;
  priority: number;
}

export interface LLMSettingsPayload {
  version: 1;
  mode: LLMEngineMode;
  active_llm_provider: LLMProviderName | null;
  providers: Partial<Record<LLMProviderName, {
    model_name: string;
    credentials: LLMCredentialInput[];
  }>>;
}

export interface LLMProviderCatalog {
  id: LLMProviderName;
  label: string;
  default_model: string;
  models: string[];
}

export interface LLMModelCatalog {
  version: number;
  providers: LLMProviderCatalog[];
}

export interface LLMCredentialStatus {
  label: string;
  masked_key: string;
  priority: number;
}

export interface LLMSettingsStatus {
  version: number;
  mode: LLMEngineMode;
  active_llm_provider: LLMProviderName | null;
  providers: Partial<Record<LLMProviderName, {
    model_name: string;
    credentials: LLMCredentialStatus[];
  }>>;
  source: 'database' | 'environment' | 'rules_only';
}

export interface LLMCredentialConnectionResult {
  label: string;
  priority: number;
  connected: boolean;
  message: string;
}

export interface LLMConnectionResult {
  connected: boolean;
  saved: boolean;
  provider: LLMProviderName;
  model_name: string;
  credentials: LLMCredentialConnectionResult[];
}

// Local persistence
export interface RecentRun {
  run_id: string;
  goal_text: string;
  status: RunStatus;
  created_at: string;
}
