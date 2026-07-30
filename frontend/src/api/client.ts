import type {
  ApiEnvelope,
  ApproveRunPayload,
  CandidatePlan,
  ClarifyRunPayload,
  CreateRunResponse,
  DemoHealth,
  DemoPortfolio,
  DemoResetResult,
  ExecutionVerification,
  ExecutionVerificationPayload,
  AdvanceEnterpriseSimulationResult,
  EnterpriseEventHistory,
  EnterpriseEventResult,
  EnterpriseScenarioList,
  EnterpriseSimulationStatusData,
  FailureService,
  FailureSimulationPayload,
  JudgeEnterpriseEventPayload,
  LLMConnectionResult,
  LLMModelCatalog,
  LLMProviderName,
  LLMSettingsPayload,
  LLMSettingsStatus,
  PreferenceSummary,
  RunSummary,
  SimulationState,
  StartEnterpriseSimulationPayload,
  StartEnterpriseSimulationResult,
  SpecialistResponseSimulationPayload,
} from '../types/api';

const BASE = '/api/v1';

function createRequestId(): string {
  if (typeof crypto !== 'undefined' && typeof crypto.randomUUID === 'function') {
    return crypto.randomUUID();
  }
  return `web-${Date.now()}-${Math.random().toString(16).slice(2)}`;
}

async function request<T>(path: string, options?: RequestInit): Promise<T> {
  const headers = new Headers(options?.headers);
  if (!headers.has('Content-Type') && options?.body) {
    headers.set('Content-Type', 'application/json');
  }
  if (!headers.has('X-Request-ID')) {
    headers.set('X-Request-ID', createRequestId());
  }

  const response = await fetch(`${BASE}${path}`, {
    ...options,
    headers,
  });

  if (!response.ok) {
    let detail = `Request failed with HTTP ${response.status}`;
    try {
      const body = await response.json() as {
        detail?: string;
        message?: string;
        errorCode?: string;
      };
      detail = body.detail ?? body.message ?? detail;
      if (body.errorCode) {
        detail = `${detail} (${body.errorCode})`;
      }
    } catch {
      // Keep the HTTP fallback when the error body is not JSON.
    }
    throw new Error(detail);
  }

  return response.json() as Promise<T>;
}

async function requestEnvelope<T>(path: string, options?: RequestInit): Promise<T> {
  const envelope = await request<ApiEnvelope<T>>(path, options);
  if (!envelope.success) {
    throw new Error(envelope.message || 'The operation did not complete successfully');
  }
  return envelope.data;
}

function normalizeCandidatePlan(plan: CandidatePlan): CandidatePlan {
  const assignments = plan.assignments ?? plan.allocations ?? [];
  const allocations = plan.allocations ?? plan.assignments ?? [];
  const profile = plan.profile || plan.profile_name || plan.profile_id || 'Unknown';
  const rawMetrics = plan.metrics ?? {};
  const rawMetadata = plan.metadata ?? {};
  const unassigned = plan.unassigned_incidents
    ?? (Array.isArray(rawMetrics.unassigned_incidents)
      ? rawMetrics.unassigned_incidents as string[]
      : []);

  return {
    ...plan,
    profile,
    description: plan.description ?? '',
    assignments,
    allocations,
    objective_value: Number(plan.objective_value ?? 0),
    unassigned_incidents: unassigned,
    metrics: {
      ...rawMetrics,
      match_rate: Number(rawMetrics.match_rate ?? 0),
      assigned_count: Number(rawMetrics.assigned_count ?? 0),
      unassigned_count: Number(rawMetrics.unassigned_count ?? unassigned.length),
      arr_protected: Number(rawMetrics.arr_protected ?? 0),
    },
    metadata: {
      ...rawMetadata,
      solver_type: rawMetadata.solver_type ?? 'CP-SAT',
      solving_time_ms: Number(rawMetadata.solving_time_ms ?? plan.solve_time_ms ?? 0),
      solver_status: rawMetadata.solver_status ?? plan.solver_status ?? 'UNKNOWN',
      fallback_status: Boolean(rawMetadata.fallback_status ?? false),
    },
    explanation: plan.explanation ?? plan.description ?? '',
  };
}

function normalizeRunSummary(summary: RunSummary): RunSummary {
  return {
    ...summary,
    candidate_plans: (summary.candidate_plans ?? []).map(normalizeCandidatePlan),
    confidence_report: summary.confidence_report ?? null,
    autonomy_risk_report: summary.autonomy_risk_report ?? null,
    replan_count: summary.replan_count ?? 0,
    excluded_specialist_incidents: summary.excluded_specialist_incidents ?? [],
    structured_goal: summary.structured_goal ?? null,
    selected_tools: summary.selected_tools ?? [],
    business_summary: summary.business_summary ?? null,
    change_summary: summary.change_summary ?? null,
    personalized_recommendation: summary.personalized_recommendation ?? null,
    candidate_plan_summary: summary.candidate_plan_summary ?? [],
  };
}

export const api = {
  // Runs
  createRun(goal_text: string): Promise<CreateRunResponse> {
    return request('/runs', {
      method: 'POST',
      body: JSON.stringify({ goal_text }),
    });
  },

  async getRunStatus(run_id: string): Promise<RunSummary> {
    const summary = await request<RunSummary>(`/runs/${encodeURIComponent(run_id)}`);
    return normalizeRunSummary(summary);
  },

  approveRun(
    run_id: string,
    payload: ApproveRunPayload,
  ): Promise<{ status: string; message: string }> {
    return request(`/runs/${encodeURIComponent(run_id)}/approve`, {
      method: 'POST',
      body: JSON.stringify(payload),
    });
  },

  clarifyRun(
    run_id: string,
    payload: ClarifyRunPayload,
  ): Promise<{ status: string; message: string }> {
    return request(`/runs/${encodeURIComponent(run_id)}/clarify`, {
      method: 'POST',
      body: JSON.stringify(payload),
    });
  },

  cancelRun(run_id: string): Promise<{ status: string; message: string }> {
    return request(`/runs/${encodeURIComponent(run_id)}/cancel`, {
      method: 'POST',
    });
  },

  getPreferenceSummary(recent_limit = 5): Promise<PreferenceSummary> {
    const limit = Math.min(20, Math.max(1, Math.trunc(recent_limit)));
    return requestEnvelope(`/preferences/summary?recent_limit=${limit}`);
  },

  verifyExecution(
    run_id: string,
    payload: ExecutionVerificationPayload,
  ): Promise<ExecutionVerification> {
    return request(`/runs/${encodeURIComponent(run_id)}/execution/verify`, {
      method: 'POST',
      body: JSON.stringify(payload),
    });
  },

  // Demo portfolio and health
  getDemoPortfolio(): Promise<DemoPortfolio> {
    return requestEnvelope('/demo/portfolio');
  },

  getDemoHealth(): Promise<DemoHealth> {
    return requestEnvelope('/demo/health');
  },

  getSimulationState(): Promise<SimulationState> {
    return requestEnvelope('/demo/simulation/state');
  },

  getEnterpriseScenarios(reload = false): Promise<EnterpriseScenarioList> {
    return requestEnvelope(`/simulation/scenarios${reload ? '?reload=true' : ''}`);
  },

  getEnterpriseSimulationStatus(): Promise<EnterpriseSimulationStatusData> {
    return requestEnvelope('/simulation/status');
  },

  startEnterpriseSimulation(
    payload: StartEnterpriseSimulationPayload,
  ): Promise<StartEnterpriseSimulationResult> {
    return requestEnvelope('/simulation/start', {
      method: 'POST',
      body: JSON.stringify(payload),
    });
  },

  pauseEnterpriseSimulation(): Promise<EnterpriseSimulationStatusData> {
    return requestEnvelope('/simulation/pause', { method: 'POST' });
  },

  resumeEnterpriseSimulation(): Promise<EnterpriseSimulationStatusData> {
    return requestEnvelope('/simulation/resume', { method: 'POST' });
  },

  resetEnterpriseSimulation(
    scenario_id?: string,
  ): Promise<EnterpriseSimulationStatusData> {
    return requestEnvelope('/simulation/reset', {
      method: 'POST',
      body: JSON.stringify(scenario_id ? { scenario_id } : {}),
    });
  },

  advanceEnterpriseSimulation(): Promise<AdvanceEnterpriseSimulationResult> {
    return requestEnvelope('/simulation/advance', { method: 'POST' });
  },

  injectEnterpriseEvent(
    payload: JudgeEnterpriseEventPayload,
  ): Promise<EnterpriseEventResult> {
    return requestEnvelope('/simulation/event', {
      method: 'POST',
      body: JSON.stringify(payload),
    });
  },

  getEnterpriseEventHistory(
    page = 1,
    pageSize = 100,
    simulationId?: string,
  ): Promise<EnterpriseEventHistory> {
    const query = new URLSearchParams({
      page: String(page),
      page_size: String(pageSize),
    });
    if (simulationId) query.set('simulation_id', simulationId);
    return requestEnvelope(`/simulation/events?${query.toString()}`);
  },

  queueSpecialistResponse(
    payload: SpecialistResponseSimulationPayload,
  ): Promise<Record<string, unknown>> {
    return requestEnvelope('/demo/simulation/specialist-response', {
      method: 'POST',
      body: JSON.stringify(payload),
    });
  },

  configureFailure(
    payload: FailureSimulationPayload,
  ): Promise<Record<string, unknown>> {
    return requestEnvelope('/demo/simulation/failure', {
      method: 'POST',
      body: JSON.stringify(payload),
    });
  },

  resetDemo(services?: FailureService[]): Promise<DemoResetResult> {
    return requestEnvelope('/demo/simulation/reset', {
      method: 'POST',
      body: JSON.stringify(services ? { services } : {}),
    });
  },

  // Secure provider settings
  getLLMModels(): Promise<LLMModelCatalog> {
    return request('/settings/llm/models');
  },

  getLLMSettings(): Promise<LLMSettingsStatus> {
    return request('/settings/llm');
  },

  testLLMSettings(
    payload: LLMSettingsPayload,
  ): Promise<LLMConnectionResult> {
    return request('/settings/llm/test', {
      method: 'POST',
      body: JSON.stringify(payload),
    });
  },

  saveLLMSettings(
    payload: LLMSettingsPayload,
  ): Promise<LLMConnectionResult> {
    return request('/settings/llm', {
      method: 'POST',
      body: JSON.stringify(payload),
    });
  },

  disconnectLLM(
    provider: LLMProviderName | null,
  ): Promise<LLMSettingsStatus> {
    return request('/settings/llm/disconnect', {
      method: 'POST',
      body: JSON.stringify({ provider }),
    });
  },

  // Legacy system surfaces retained while existing components migrate.
  getSystemHealth(): Promise<Record<string, unknown>> {
    return request('/system/health');
  },

  resetSystem(): Promise<{ status: string }> {
    return request('/control-room/reset', { method: 'POST' });
  },
};
