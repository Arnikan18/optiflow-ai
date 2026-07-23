export type FreshnessStatus = 'FRESH' | 'STALE_ALLOWED' | 'STALE_BLOCKING' | 'MISSING' | 'CONFLICTING' | 'INVALID';

export type FailureMode = 'NONE' | 'TIMEOUT' | 'HTTP_500' | 'MALFORMED_RESPONSE' | 'EMPTY_RESPONSE';

export type EscalationStatus = 'OPEN' | 'ASSIGNED' | 'IN_PROGRESS' | 'MONITORING' | 'RESOLVED';

export type AssignmentRequestStatus = 'PENDING' | 'ACCEPTED' | 'REJECTED' | 'EXPIRED';

export interface CustomerState {
  customer_id: string;
  name: string;
  annual_recurring_revenue: number | null;
  tier: string | null;
  renewal_date: string | null; // ISO Date String
  strategic_account: boolean;
  commercial_dependencies: any[];
  evidence_ids: string[];
}

export interface EscalationState {
  escalation_id: string;
  customer_id: string;
  title: string;
  severity: string;
  sla_deadline: string | null; // ISO Date String
  status: EscalationStatus;
  required_skills: string[];
  required_access: string[];
  required_duration_minutes: number | null;
  workaround_status: string;
  current_specialist_id: string | null;
  postponement_count: number;
  evidence_ids: string[];
}

export interface SpecialistState {
  specialist_id: string;
  name: string;
  skills: string[];
  access_permissions: string[];
  available_from: string | null;
  available_until: string | null;
  available_minutes: number | null;
  current_assignment_count: number;
  maximum_concurrent_assignments: number;
  after_hours_minutes: number;
  overnight_incident_count: number;
  recent_interruption_count: number;
  protected_emergency_minutes: number;
  evidence_ids: string[];
}

export interface EnterpriseState {
  snapshot_id: string;
  run_id: string;
  state_version: number;
  generated_at: string; // ISO Date String
  time_horizon_minutes: number;
  customers: CustomerState[];
  escalations: EscalationState[];
  specialists: SpecialistState[];
  missing_fields: any[];
  conflicts: any[];
  evidence_quality: {
    completeness: number;
    freshness: number;
    consistency: number;
  };
  evidence_ids: string[];
}
