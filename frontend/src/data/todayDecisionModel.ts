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

function clampPercentage(value: number): number {
  return Math.max(0, Math.min(100, Math.round(value)));
}

function deadlineSignal(
  incident: DemoIncident,
  now: Date,
): { signal: PressureSignal | null; label: string; remainingMs: number | null } {
  if (!incident.sla_deadline) {
    return {
      signal: incident.sla_risk
        ? {
            id: 'sla-risk',
            label: 'SLA pressure',
            detail: 'The source reports SLA risk without a usable deadline.',
            weight: 20,
          }
        : null,
      label: 'No deadline',
      remainingMs: null,
    };
  }

  const deadline = new Date(incident.sla_deadline);
  const remainingMs = deadline.getTime() - now.getTime();
  if (Number.isNaN(remainingMs)) {
    return { signal: null, label: 'Invalid deadline', remainingMs: null };
  }

  const absoluteMinutes = Math.max(1, Math.round(Math.abs(remainingMs) / 60_000));
  const duration = absoluteMinutes < 60
    ? `${absoluteMinutes}m`
    : absoluteMinutes < 1_440
      ? `${Math.round(absoluteMinutes / 60)}h`
      : `${Math.round(absoluteMinutes / 1_440)}d`;

  if (remainingMs <= 0) {
    return {
      signal: {
        id: 'sla-overdue',
        label: 'SLA overdue',
        detail: `The recorded SLA deadline passed ${duration} ago.`,
        weight: 45,
      },
      label: `${duration} overdue`,
      remainingMs,
    };
  }

  if (remainingMs <= 60 * 60_000) {
    return {
      signal: {
        id: 'sla-one-hour',
        label: 'SLA within one hour',
        detail: `Only ${duration} remains before the recorded SLA deadline.`,
        weight: 40,
      },
      label: `${duration} to SLA`,
      remainingMs,
    };
  }

  if (remainingMs <= 4 * 60 * 60_000) {
    return {
      signal: {
        id: 'sla-four-hours',
        label: 'SLA within four hours',
        detail: `${duration} remains before the recorded SLA deadline.`,
        weight: 30,
      },
      label: `${duration} to SLA`,
      remainingMs,
    };
  }

  if (remainingMs <= 24 * 60 * 60_000 || incident.sla_risk) {
    return {
      signal: {
        id: 'sla-today',
        label: 'SLA pressure today',
        detail: `${duration} remains before the recorded SLA deadline.`,
        weight: 20,
      },
      label: `${duration} to SLA`,
      remainingMs,
    };
  }

  return { signal: null, label: `${duration} to SLA`, remainingMs };
}

function severitySignal(severity: string | null): PressureSignal | null {
  const value = normaliseStatus(severity);
  const weights: Record<string, number> = {
    CRITICAL: 35,
    HIGH: 25,
    MEDIUM: 15,
    LOW: 5,
  };
  const weight = weights[value];
  if (!weight) return null;

  return {
    id: `severity-${value.toLowerCase()}`,
    label: `${value.toLowerCase()} severity`,
    detail: `The incident source records ${value.toLowerCase()} severity.`,
    weight,
  };
}

function commercialSignal(customer: DemoCustomer | null): PressureSignal | null {
  const value = customer?.business_value ?? customer?.arr ?? 0;
  if (value >= 1_000_000) {
    return {
      id: 'commercial-1m',
      label: 'Very high commercial exposure',
      detail: 'At least $1m in represented customer value is connected to this incident.',
      weight: 12,
    };
  }
  if (value >= 500_000) {
    return {
      id: 'commercial-500k',
      label: 'High commercial exposure',
      detail: 'At least $500k in represented customer value is connected to this incident.',
      weight: 9,
    };
  }
  if (value >= 250_000) {
    return {
      id: 'commercial-250k',
      label: 'Material commercial exposure',
      detail: 'At least $250k in represented customer value is connected to this incident.',
      weight: 6,
    };
  }
  if (value >= 100_000) {
    return {
      id: 'commercial-100k',
      label: 'Commercial exposure',
      detail: 'At least $100k in represented customer value is connected to this incident.',
      weight: 3,
    };
  }
  return null;
}

function pressureBand(score: number): PressureBand {
  if (score >= 90) return 'critical';
  if (score >= 65) return 'urgent';
  if (score >= 40) return 'watch';
  return 'routine';
}

export function deriveTodayProblems(
  portfolio: DemoPortfolio,
  now = new Date(),
): TodayProblem[] {
  const customers = new Map(
    portfolio.customers.map((customer) => [customer.customer_id, customer]),
  );

  const problems = portfolio.incidents
    .filter((incident) => !CLOSED_STATUSES.has(normaliseStatus(incident.status)))
    .map((incident) => {
      const customer = customers.get(incident.customer_id) ?? null;
      const deadline = deadlineSignal(incident, now);
      const signals: PressureSignal[] = [];

      if (deadline.signal) signals.push(deadline.signal);

      const severity = severitySignal(incident.severity);
      if (severity) signals.push(severity);

      if (!incident.current_specialist_id) {
        signals.push({
          id: 'unassigned',
          label: 'No confirmed owner',
          detail: 'The incident has no current specialist assignment.',
          weight: 20,
        });
      }

      if (customer?.renewal_risk) {
        signals.push({
          id: 'renewal-risk',
          label: 'Renewal risk',
          detail: 'CRM reports that this customer currently carries renewal risk.',
          weight: 12,
        });
      }

      const commercial = commercialSignal(customer);
      if (commercial) signals.push(commercial);

      if ((incident.age_hours ?? 0) >= 48) {
        signals.push({
          id: 'long-running',
          label: 'Long-running incident',
          detail: 'The incident has remained open for at least 48 hours.',
          weight: 5,
        });
      }

      signals.sort((left, right) => right.weight - left.weight);
      const score = signals.reduce((total, signal) => total + signal.weight, 0);

      return {
        rank: 0,
        score,
        band: pressureBand(score),
        incident,
        customer,
        signals,
        topReasons: signals.slice(0, 2).map((signal) => signal.label),
        deadlineLabel: deadline.label,
        commercialExposure: customer?.business_value ?? customer?.arr ?? null,
        remainingMs: deadline.remainingMs,
      };
    })
    .sort((left, right) => (
      right.score - left.score
      || (left.remainingMs ?? Number.POSITIVE_INFINITY)
        - (right.remainingMs ?? Number.POSITIVE_INFINITY)
      || left.incident.incident_id.localeCompare(right.incident.incident_id)
    ));

  return problems.map(({ remainingMs: _remainingMs, ...problem }, index) => ({
    ...problem,
    rank: index + 1,
  }));
}

export function deriveWorkerReadiness(specialist: DemoSpecialist): WorkerReadiness {
  const capacity = Math.max(0, specialist.capacity ?? 0);
  const current = Math.max(0, specialist.current_workload ?? 0);
  const reserved = Math.max(0, specialist.reserved_workload ?? 0);
  const usedCapacity = current + reserved;
  const remainingCapacity = Math.max(0, capacity - usedCapacity);
  const utilisation = clampPercentage(
    specialist.utilisation_percentage
      ?? (capacity > 0 ? (usedCapacity / capacity) * 100 : 100),
  );
  const available = specialist.availability === true;
  const reasons: string[] = [];

  if (!available) reasons.push('Not available for new work');
  if (remainingCapacity === 0) reasons.push('No remaining capacity');
  if (reserved > 0) reasons.push(`${reserved} slot${reserved === 1 ? '' : 's'} tentatively reserved`);
  if (remainingCapacity > 0) reasons.push(`${remainingCapacity} slot${remainingCapacity === 1 ? '' : 's'} free`);
  if (specialist.skills.length > 0) reasons.push(`${specialist.skills.length} recorded skills`);

  let state: ReadinessState;
  if (!available) {
    state = 'unavailable';
  } else if (remainingCapacity === 0) {
    state = 'saturated';
  } else if (utilisation >= 75 || reserved > 0) {
    state = 'limited';
  } else {
    state = 'ready';
  }

  const capacityScore = capacity > 0 ? (remainingCapacity / capacity) * 35 : 0;
  const headroomScore = Math.max(0, 100 - utilisation) * 0.2;
  const skillVisibilityScore = specialist.skills.length > 0 ? 10 : 0;
  const score = available
    ? clampPercentage(35 + capacityScore + headroomScore + skillVisibilityScore)
    : 0;

  return {
    specialist,
    score,
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
      right.score - left.score
      || left.specialist.specialist_name.localeCompare(right.specialist.specialist_name)
    ));
}

export function buildGoalFromProblems(problems: TodayProblem[]): string {
  if (problems.length === 0) {
    return 'Review today\'s portfolio pressure and protect service outcomes without exceeding safe team capacity.';
  }

  const selected = problems.slice(0, 3);
  const customers = Array.from(new Set(
    selected
      .map((problem) => problem.customer?.customer_name)
      .filter((name): name is string => Boolean(name)),
  ));
  const customerPhrase = customers.length > 0
    ? customers.join(', ')
    : 'the highest-pressure customers';

  return `Protect ${customerPhrase} from today\'s highest service risks while keeping every specialist within available capacity.`;
}
