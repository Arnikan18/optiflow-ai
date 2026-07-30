import type {
  DemoCustomer,
  DemoIncident,
  DemoPortfolio,
  DemoSpecialist,
} from '../types/api';

export type PressureBand = 'critical' | 'urgent' | 'watch' | 'routine';
export type ReadinessState = 'ready' | 'limited' | 'saturated' | 'unavailable';

export interface PressureSignal {
  id: string;
  label: string;
  detail: string;
  weight: number;
}

export interface TodayProblem {
  rank: number;
  score: number;
  band: PressureBand;
  incident: DemoIncident;
  customer: DemoCustomer | null;
  signals: PressureSignal[];
  topReasons: string[];
  deadlineLabel: string;
  commercialExposure: number | null;
}

export interface WorkerReadiness {
  specialist: DemoSpecialist;
  score: number;
  state: ReadinessState;
  remainingCapacity: number;
  usedCapacity: number;
  reservedCapacity: number;
  utilisation: number;
  reasons: string[];
}

const CLOSED_STATUSES = new Set(['CLOSED', 'RESOLVED', 'CANCELLED']);

function normaliseStatus(value: string | null): string {
  return value?.trim().toUpperCase() ?? '';
}

function pressureBand(score: number): PressureBand {
  if (score >= 85) return 'critical';
  if (score >= 65) return 'urgent';
  if (score >= 40) return 'watch';
  return 'routine';
}

function deadlineLabel(minutes: number | null): string {
  if (minutes === null) return 'No SLA time';
  const absolute = Math.abs(minutes);
  const duration = absolute < 60
    ? `${absolute}m`
    : absolute < 1_440
      ? `${Math.round(absolute / 60)}h`
      : `${Math.round(absolute / 1_440)}d`;
  return minutes <= 0 ? `${duration} overdue` : `${duration} to SLA`;
}

export function deriveTodayProblems(portfolio: DemoPortfolio): TodayProblem[] {
  const customers = new Map(
    portfolio.customers.map((customer) => [customer.customer_id, customer]),
  );

  return portfolio.incidents
    .filter((incident) => !CLOSED_STATUSES.has(normaliseStatus(incident.status)))
    .map((incident, index) => {
      const score = incident.priority_score ?? 0;
      const signals = incident.priority_signals.map((signal) => ({
        id: signal.key,
        label: signal.label,
        detail: `${signal.points} priority points from live operational data.`,
        weight: signal.points,
      }));

      return {
        rank: incident.priority_rank ?? index + 1,
        score,
        band: pressureBand(score),
        incident,
        customer: customers.get(incident.customer_id) ?? null,
        signals,
        topReasons: signals.slice(0, 2).map((signal) => signal.label),
        deadlineLabel: deadlineLabel(incident.minutes_to_sla),
        commercialExposure: incident.arr_exposure,
      };
    })
    .sort((left, right) => left.rank - right.rank);
}

export function deriveWorkerReadiness(specialist: DemoSpecialist): WorkerReadiness {
  const capacity = Math.max(0, specialist.capacity ?? 0);
  const current = Math.max(0, specialist.current_workload ?? 0);
  const reserved = Math.max(0, specialist.reserved_workload ?? 0);
  const usedCapacity = current + reserved;
  const remainingCapacity = Math.max(
    0,
    specialist.available_capacity ?? capacity - usedCapacity,
  );
  const utilisation = Math.max(
    0,
    Math.min(
      100,
      Math.round(
        specialist.utilisation_percentage
          ?? (capacity > 0 ? (usedCapacity / capacity) * 100 : 100),
      ),
    ),
  );
  const operational = specialist.operationally_available
    ?? (specialist.availability === true && remainingCapacity > 0);

  let state: ReadinessState;
  if (!specialist.availability) {
    state = 'unavailable';
  } else if (!operational || remainingCapacity === 0) {
    state = 'saturated';
  } else if (reserved > 0 || utilisation >= 75) {
    state = 'limited';
  } else {
    state = 'ready';
  }

  const reasons = [
    `${remainingCapacity}/${capacity} capacity free`,
    specialist.sla_success_rate_30d === null
      ? 'SLA history unavailable'
      : `${specialist.sla_success_rate_30d}% SLA success`,
    `${specialist.completed_assignments_30d} completed in 30 days`,
  ];

  return {
    specialist,
    score: Math.round(specialist.effectiveness_score ?? 0),
    state,
    remainingCapacity,
    usedCapacity,
    reservedCapacity: reserved,
    utilisation,
    reasons,
  };
}

export function deriveTeamReadiness(portfolio: DemoPortfolio): WorkerReadiness[] {
  return portfolio.specialists
    .map(deriveWorkerReadiness)
    .sort((left, right) => (
      Number(right.specialist.operationally_available === true)
        - Number(left.specialist.operationally_available === true)
      || right.score - left.score
      || left.specialist.specialist_name.localeCompare(right.specialist.specialist_name)
    ));
}

export function buildGoalFromProblems(problems: TodayProblem[]): string {
  if (problems.length === 0) {
    return 'Review today\'s portfolio pressure and protect service outcomes without exceeding safe team capacity.';
  }

  const customers = Array.from(new Set(
    problems
      .slice(0, 3)
      .map((problem) => problem.customer?.customer_name)
      .filter((name): name is string => Boolean(name)),
  ));

  return `Protect ${customers.join(', ') || 'the highest-pressure customers'} from today\'s highest service risks while keeping every specialist within available capacity.`;
}
