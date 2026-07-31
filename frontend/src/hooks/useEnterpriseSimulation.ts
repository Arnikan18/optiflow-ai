import {
  createContext,
  createElement,
  useCallback,
  useContext,
  useEffect,
  useRef,
  useState,
  type ReactNode,
} from 'react';
import { api } from '../api/client';
import type {
  DemoPortfolio,
  EnterpriseEventHistory,
  EnterpriseScenario,
  EnterpriseSimulationMode,
  EnterpriseSimulationStatusData,
  JudgeEnterpriseEventPayload,
} from '../types/api';

export type SimulationAction =
  | 'start'
  | 'pause'
  | 'resume'
  | 'reset'
  | 'advance'
  | 'inject';

export interface EnterprisePortfolioDelta {
  detectedAt: string;
  customerIds: string[];
  incidentIds: string[];
  specialistIds: string[];
  urgentBefore: number;
  urgentAfter: number;
  availableBefore: number;
  availableAfter: number;
}

interface UseEnterpriseSimulationResult {
  scenarios: EnterpriseScenario[];
  defaultScenarioId: string | null;
  status: EnterpriseSimulationStatusData | null;
  events: Array<Record<string, unknown>>;
  portfolio: DemoPortfolio | null;
  portfolioDelta: EnterprisePortfolioDelta | null;
  loading: boolean;
  refreshing: boolean;
  busyAction: SimulationAction | null;
  error: string | null;
  refresh: () => Promise<void>;
  start: (scenarioId: string, mode: EnterpriseSimulationMode) => Promise<boolean>;
  pause: () => Promise<boolean>;
  resume: () => Promise<boolean>;
  reset: (scenarioId?: string) => Promise<boolean>;
  advance: () => Promise<boolean>;
  inject: (payload: JudgeEnterpriseEventPayload) => Promise<boolean>;
  clearError: () => void;
}

const ACTIVE_INCIDENT_STATUSES = new Set(['OPEN', 'IN_PROGRESS', 'PENDING']);
const URGENT_SEVERITIES = new Set(['CRITICAL', 'HIGH']);

function urgentIncidentCount(portfolio: DemoPortfolio): number {
  return portfolio.incidents.filter((incident) => (
    ACTIVE_INCIDENT_STATUSES.has(incident.status?.toUpperCase() ?? '')
    && URGENT_SEVERITIES.has(incident.severity?.toUpperCase() ?? '')
  )).length;
}

function changedIds<T>(
  previousItems: T[],
  nextItems: T[],
  idFor: (item: T) => string,
  comparableFor: (item: T) => unknown,
): string[] {
  const previous = new Map(
    previousItems.map((item) => [idFor(item), JSON.stringify(comparableFor(item))]),
  );
  const next = new Map(
    nextItems.map((item) => [idFor(item), JSON.stringify(comparableFor(item))]),
  );
  const identifiers = new Set([...previous.keys(), ...next.keys()]);

  return Array.from(identifiers).filter((identifier) => (
    previous.get(identifier) !== next.get(identifier)
  ));
}

function buildPortfolioDelta(
  previous: DemoPortfolio,
  next: DemoPortfolio,
): EnterprisePortfolioDelta | null {
  const customerIds = changedIds(
    previous.customers,
    next.customers,
    (customer) => customer.customer_id,
    (customer) => ({
      arr: customer.arr,
      businessValue: customer.business_value,
      renewalRisk: customer.renewal_risk,
      strategicPriority: customer.strategic_priority,
      incidents: customer.current_incident_count,
    }),
  );
  const incidentIds = changedIds(
    previous.incidents,
    next.incidents,
    (incident) => incident.incident_id,
    (incident) => ({
      customerId: incident.customer_id,
      severity: incident.severity,
      status: incident.status,
      deadline: incident.sla_deadline,
      risk: incident.sla_risk,
      effort: incident.estimated_effort_minutes,
      requiredSkills: incident.required_skills,
      priorityScore: incident.priority_score,
      owner: incident.current_specialist_id,
      assignment: incident.assignment_status,
    }),
  );
  const specialistIds = changedIds(
    previous.specialists,
    next.specialists,
    (specialist) => specialist.specialist_id,
    (specialist) => ({
      available: specialist.availability,
      capacity: specialist.capacity,
      workload: specialist.current_workload,
      reserved: specialist.reserved_workload,
      utilisation: specialist.utilisation_percentage,
    }),
  );

  if (customerIds.length === 0 && incidentIds.length === 0 && specialistIds.length === 0) {
    return null;
  }

  return {
    detectedAt: next.generated_at,
    customerIds,
    incidentIds,
    specialistIds,
    urgentBefore: urgentIncidentCount(previous),
    urgentAfter: urgentIncidentCount(next),
    availableBefore: previous.portfolio_summary.available_specialists ?? 0,
    availableAfter: next.portfolio_summary.available_specialists ?? 0,
  };
}

function errorMessage(caught: unknown): string {
  return caught instanceof Error
    ? caught.message
    : 'The live enterprise demo could not complete this action.';
}

function useEnterpriseSimulationController(
  pollIntervalMs = 3_000,
): UseEnterpriseSimulationResult {
  const [scenarios, setScenarios] = useState<EnterpriseScenario[]>([]);
  const [defaultScenarioId, setDefaultScenarioId] = useState<string | null>(null);
  const [status, setStatus] = useState<EnterpriseSimulationStatusData | null>(null);
  const [history, setHistory] = useState<EnterpriseEventHistory | null>(null);
  const [portfolio, setPortfolio] = useState<DemoPortfolio | null>(null);
  const [portfolioDelta, setPortfolioDelta] = useState<EnterprisePortfolioDelta | null>(null);
  const [loading, setLoading] = useState(true);
  const [refreshing, setRefreshing] = useState(false);
  const [busyAction, setBusyAction] = useState<SimulationAction | null>(null);
  const [error, setError] = useState<string | null>(null);
  const mountedRef = useRef(true);
  const portfolioRef = useRef<DemoPortfolio | null>(null);
  const refreshInFlightRef = useRef(false);

  const refreshRuntime = useCallback(async () => {
    if (refreshInFlightRef.current) return;
    refreshInFlightRef.current = true;
    setRefreshing(true);

    try {
      const [nextStatus, nextHistory, nextPortfolio] = await Promise.all([
        api.getEnterpriseSimulationStatus(),
        api.getEnterpriseEventHistory(),
        api.getDemoPortfolio(),
      ]);
      if (!mountedRef.current) return;

      if (portfolioRef.current) {
        const delta = buildPortfolioDelta(portfolioRef.current, nextPortfolio);
        if (delta) setPortfolioDelta(delta);
      }
      portfolioRef.current = nextPortfolio;
      setStatus(nextStatus);
      setHistory(nextHistory);
      setPortfolio(nextPortfolio);
      setError(null);
    } catch (caught: unknown) {
      if (mountedRef.current) setError(errorMessage(caught));
    } finally {
      refreshInFlightRef.current = false;
      if (mountedRef.current) {
        setRefreshing(false);
        setLoading(false);
      }
    }
  }, []);

  const refreshScenarios = useCallback(async () => {
    try {
      const result = await api.getEnterpriseScenarios();
      if (!mountedRef.current) return;
      setScenarios(result.scenarios);
      setDefaultScenarioId(result.default_scenario_id);
    } catch (caught: unknown) {
      if (mountedRef.current) setError(errorMessage(caught));
    }
  }, []);

  const refresh = useCallback(async () => {
    await Promise.all([refreshScenarios(), refreshRuntime()]);
  }, [refreshRuntime, refreshScenarios]);

  const perform = useCallback(async (
    action: SimulationAction,
    operation: () => Promise<unknown>,
  ): Promise<boolean> => {
    if (busyAction) return false;
    setBusyAction(action);
    setError(null);
    try {
      await operation();
      await refreshRuntime();
      return true;
    } catch (caught: unknown) {
      if (mountedRef.current) setError(errorMessage(caught));
      return false;
    } finally {
      if (mountedRef.current) setBusyAction(null);
    }
  }, [busyAction, refreshRuntime]);

  useEffect(() => {
    mountedRef.current = true;
    void refresh();
    const timer = window.setInterval(() => {
      void refreshRuntime();
    }, pollIntervalMs);

    return () => {
      mountedRef.current = false;
      window.clearInterval(timer);
    };
  }, [pollIntervalMs, refresh, refreshRuntime]);

  const controller: UseEnterpriseSimulationResult = {
    scenarios,
    defaultScenarioId,
    status,
    events: history?.events ?? [],
    portfolio,
    portfolioDelta,
    loading,
    refreshing,
    busyAction,
    error,
    refresh,
    start: (scenarioId, mode) => perform('start', () => api.startEnterpriseSimulation({
      scenario_id: scenarioId,
      mode,
      reset_existing: true,
      auto_advance: mode === 'TIMELINE',
    })),
    pause: () => perform('pause', () => api.pauseEnterpriseSimulation()),
    resume: () => perform('resume', () => api.resumeEnterpriseSimulation()),
    reset: (scenarioId) => perform('reset', () => api.resetEnterpriseSimulation(scenarioId)),
    advance: () => perform('advance', () => api.advanceEnterpriseSimulation()),
    inject: (payload) => perform('inject', () => api.injectEnterpriseEvent(payload)),
    clearError: () => setError(null),
  };

  useEffect(() => {
    if (
      status?.status !== 'RUNNING'
      || status.mode !== 'TIMELINE'
      || status.pending_events.length === 0
      || busyAction !== null
    ) {
      return;
    }
    const timer = window.setTimeout(() => {
      void perform('advance', () => api.advanceEnterpriseSimulation());
    }, 10_000);
    return () => window.clearTimeout(timer);
  }, [
    busyAction,
    perform,
    status?.current_timeline_position,
    status?.mode,
    status?.pending_events.length,
    status?.status,
  ]);

  return controller;
}

const EnterpriseSimulationContext = createContext<UseEnterpriseSimulationResult | null>(null);

export function EnterpriseSimulationProvider({ children }: { children: ReactNode }) {
  const simulation = useEnterpriseSimulationController();
  return createElement(EnterpriseSimulationContext.Provider, { value: simulation }, children);
}

export function useEnterpriseSimulation(): UseEnterpriseSimulationResult {
  const simulation = useContext(EnterpriseSimulationContext);
  if (!simulation) {
    throw new Error('useEnterpriseSimulation must be used inside EnterpriseSimulationProvider');
  }
  return simulation;
}
