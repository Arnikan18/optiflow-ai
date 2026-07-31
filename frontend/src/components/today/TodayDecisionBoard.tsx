import { useCallback, useEffect, useMemo, useState } from 'react';
import { api } from '../../api/client';
import {
  buildGoalFromProblems,
  deriveTeamReadiness,
  deriveTodayProblems,
  type PressureBand,
  type TodayProblem,
  type WorkerReadiness,
} from '../../data/todayDecisionModel';
import type { DemoIncident, DemoPortfolio } from '../../types/api';
import { GoalInput } from '../run/GoalInput';

const BAND_STYLE: Record<PressureBand, {
  label: string;
  border: string;
  text: string;
  dot: string;
  wash: string;
}> = {
  critical: {
    label: 'Critical',
    border: 'border-ops-rose/40',
    text: 'text-ops-rose',
    dot: 'bg-ops-rose',
    wash: 'bg-ops-rose/[0.055]',
  },
  urgent: {
    label: 'Urgent',
    border: 'border-ops-orange/40',
    text: 'text-ops-orange',
    dot: 'bg-ops-orange',
    wash: 'bg-ops-orange/[0.05]',
  },
  watch: {
    label: 'Watch',
    border: 'border-ops-amber/35',
    text: 'text-ops-amber',
    dot: 'bg-ops-amber',
    wash: 'bg-ops-amber/[0.045]',
  },
  routine: {
    label: 'Routine',
    border: 'border-border-dim',
    text: 'text-ops-cyan',
    dot: 'bg-ops-cyan',
    wash: 'bg-deep/50',
  },
};

const WORKER_STYLE = {
  ready: { label: 'Ready', dot: 'bg-ops-emerald', text: 'text-ops-emerald' },
  limited: { label: 'Limited', dot: 'bg-ops-amber', text: 'text-ops-amber' },
  saturated: { label: 'Full', dot: 'bg-ops-rose', text: 'text-ops-rose' },
  unavailable: { label: 'Away', dot: 'bg-ink-muted', text: 'text-ink-muted' },
} as const;

function Chevron({ open }: { open: boolean }) {
  return (
    <svg
      viewBox="0 0 20 20"
      fill="none"
      stroke="currentColor"
      strokeWidth="1.8"
      className={`h-5 w-5 transition-transform ${open ? 'rotate-180' : ''}`}
      aria-hidden="true"
    >
      <path d="m5 7.5 5 5 5-5" />
    </svg>
  );
}

function RefreshIcon({ spinning = false }: { spinning?: boolean }) {
  return (
    <svg
      viewBox="0 0 24 24"
      fill="none"
      stroke="currentColor"
      strokeWidth="1.8"
      strokeLinecap="round"
      className={`h-5 w-5 ${spinning ? 'animate-spin' : ''}`}
      aria-hidden="true"
    >
      <path d="M20 11a8 8 0 0 0-14.9-4M4 4v5h5M4 13a8 8 0 0 0 14.9 4M20 20v-5h-5" />
    </svg>
  );
}

function initials(name: string): string {
  return name
    .split(/\s+/)
    .slice(0, 2)
    .map((part) => part[0]?.toUpperCase())
    .join('');
}

function formatMoney(value: number | null): string {
  if (value === null) return '—';
  if (value >= 1_000_000) return `$${(value / 1_000_000).toFixed(1)}m`;
  if (value >= 1_000) return `$${Math.round(value / 1_000)}k`;
  return `$${Math.round(value)}`;
}

function Metric({
  label,
  value,
  tone = 'text-ink-primary',
}: {
  label: string;
  value: string;
  tone?: string;
}) {
  return (
    <div className="min-w-0">
      <p className={`text-lg font-extrabold tracking-[-0.03em] ${tone}`}>{value}</p>
      <p className="mt-0.5 text-xs text-ink-muted">{label}</p>
    </div>
  );
}

function WorkerButton({
  worker,
  assignedProblems,
  open,
  onClick,
}: {
  worker: WorkerReadiness;
  assignedProblems: DemoIncident[];
  open: boolean;
  onClick: () => void;
}) {
  const style = WORKER_STYLE[worker.state];
  const effectiveness = worker.specialist.effectiveness_score;

  return (
    <button
      type="button"
      onClick={onClick}
      aria-expanded={open}
      className={`w-[240px] shrink-0 rounded-2xl border p-4 text-left transition-all focus-ring ${
        open
          ? 'border-ops-cyan bg-ops-cyan/[0.07] shadow-card'
          : 'border-border-dim bg-abyss hover:border-border-base'
      }`}
    >
      <div className="flex items-center gap-3">
        <span className="flex h-11 w-11 shrink-0 items-center justify-center rounded-full border border-border-base bg-deep text-sm font-extrabold text-ink-primary">
          {initials(worker.specialist.specialist_name)}
        </span>
        <span className="min-w-0">
          <span className="block truncate text-sm font-extrabold text-ink-primary">
            {worker.specialist.specialist_name}
          </span>
          <span className={`mt-1 flex items-center gap-1.5 text-xs font-bold ${style.text}`}>
            <span className={`h-2 w-2 rounded-full ${style.dot}`} />
            {style.label}
            {assignedProblems.length > 0 && (
              <span className="text-ink-muted">· {assignedProblems.length} active</span>
            )}
          </span>
        </span>
      </div>

      <div className="mt-4 grid grid-cols-3 gap-3 border-t border-border-dim pt-3">
        <div>
          <p className="text-base font-extrabold text-ink-primary">
            {effectiveness === null ? '—' : `${Math.round(effectiveness)}%`}
          </p>
          <p className="text-xs text-ink-muted">effectiveness</p>
        </div>
        <div>
          <p className="text-base font-extrabold text-ink-primary">
            {assignedProblems.length}
          </p>
          <p className="text-xs text-ink-muted">active work</p>
        </div>
        <div>
          <p className="text-base font-extrabold text-ink-primary">
            {worker.remainingCapacity}/{worker.specialist.capacity ?? 0}
          </p>
          <p className="text-xs text-ink-muted">free</p>
        </div>
      </div>
    </button>
  );
}

function WorkerDetail({
  worker,
  assignedProblems,
}: {
  worker: WorkerReadiness;
  assignedProblems: DemoIncident[];
}) {
  const specialist = worker.specialist;

  return (
    <div className="mt-3 rounded-2xl border border-ops-cyan/30 bg-ops-cyan/[0.045] p-5 animate-fade-in">
      <div className="flex flex-wrap items-start justify-between gap-4">
        <div>
          <p className="text-base font-extrabold text-ink-primary">{specialist.specialist_name}</p>
          <p className="mt-1 text-sm text-ink-muted">
            {specialist.completed_assignments_30d} completed assignments · last 30 days
          </p>
        </div>
        <span className="rounded-full border border-border-base bg-abyss px-3 py-1 text-xs font-bold text-ink-secondary">
          {assignedProblems.length} active work · {worker.remainingCapacity} capacity free
        </span>
      </div>

      <div className="mt-5 border-t border-border-dim pt-4">
        <p className="text-xs font-bold uppercase tracking-[0.12em] text-ink-muted">Current work</p>
        {assignedProblems.length > 0 ? (
          <div className="mt-3 grid gap-2 sm:grid-cols-2">
            {assignedProblems.map((incident) => (
              <div
                key={incident.incident_id}
                className="rounded-xl border border-border-dim bg-abyss px-4 py-3"
              >
                <div className="flex items-start justify-between gap-3">
                  <div className="min-w-0">
                    <p className="truncate text-sm font-bold text-ink-primary">
                      {incident.title ?? incident.incident_id}
                    </p>
                    <p className="mt-1 truncate text-xs text-ink-muted">
                      {incident.customer_name ?? incident.customer_id}
                    </p>
                  </div>
                  <span className="shrink-0 rounded-full bg-ops-cyan/10 px-2 py-1 text-xs font-bold text-ops-cyan">
                    {incident.status?.replace(/_/g, ' ') ?? 'Assigned'}
                  </span>
                </div>
              </div>
            ))}
          </div>
        ) : (
          <p className="mt-3 text-sm text-ink-muted">
            {worker.usedCapacity > 0
              ? `${worker.usedCapacity} capacity ${worker.usedCapacity === 1 ? 'unit is' : 'units are'} used by work outside this escalation portfolio.`
              : 'No active incident is assigned.'}
          </p>
        )}
      </div>

      <div className="mt-5 grid grid-cols-2 gap-4 sm:grid-cols-4">
        <Metric
          label="SLA success"
          value={specialist.sla_success_rate_30d === null ? '—' : `${specialist.sla_success_rate_30d}%`}
          tone="text-ops-emerald"
        />
        <Metric
          label="Acceptance"
          value={specialist.assignment_acceptance_rate_30d === null ? '—' : `${specialist.assignment_acceptance_rate_30d}%`}
        />
        <Metric
          label="Capacity reliability"
          value={specialist.capacity_reliability_rate_30d === null ? '—' : `${specialist.capacity_reliability_rate_30d}%`}
        />
        <Metric
          label="Average resolution"
          value={specialist.average_resolution_minutes_30d === null ? '—' : `${specialist.average_resolution_minutes_30d}m`}
        />
      </div>

      <div className="mt-5 flex flex-wrap gap-2 border-t border-border-dim pt-4">
        {specialist.skills.map((skill) => (
          <span
            key={skill}
            className="rounded-full border border-border-dim bg-abyss px-3 py-1 text-xs font-semibold text-ink-secondary"
          >
            {skill}
          </span>
        ))}
      </div>
    </div>
  );
}

function ProblemRow({
  problem,
  open,
  onOpen,
}: {
  problem: TodayProblem;
  open: boolean;
  onOpen: () => void;
}) {
  const style = BAND_STYLE[problem.band];
  const title = problem.incident.title ?? problem.incident.summary ?? problem.incident.incident_id;
  const suggestedGoal = buildGoalFromProblems([problem]);

  return (
    <article className={`overflow-hidden rounded-2xl border ${style.border} ${style.wash}`}>
      <div className="flex items-stretch">
        <button
          type="button"
          onClick={onOpen}
          aria-expanded={open}
          className="grid min-h-20 min-w-0 flex-1 grid-cols-[auto_minmax(0,1fr)_auto] items-center gap-4 p-4 text-left focus-ring sm:grid-cols-[auto_minmax(0,1fr)_120px_90px_auto]"
        >
          <span className={`flex h-10 w-10 items-center justify-center rounded-xl border ${style.border} bg-abyss text-base font-extrabold ${style.text}`}>
            {problem.rank}
          </span>

          <span className="min-w-0">
            <span className={`flex items-center gap-2 text-sm font-bold ${style.text}`}>
              <span className={`h-2 w-2 rounded-full ${style.dot}`} />
              {style.label}
            </span>
            <span className="mt-1 block truncate text-base font-extrabold text-ink-primary">{title}</span>
            <span className="mt-1 block truncate text-sm text-ink-muted">
              {problem.incident.customer_name ?? problem.customer?.customer_name ?? problem.incident.customer_id}
            </span>
          </span>

          <span className="hidden sm:block">
            <span className={`block text-base font-extrabold ${style.text}`}>{problem.deadlineLabel}</span>
            <span className="mt-1 block text-sm text-ink-muted">SLA clock</span>
          </span>

          <span className="hidden sm:block">
            <span className="block text-base font-extrabold text-ink-primary">{problem.score}</span>
            <span className="mt-1 block text-sm text-ink-muted">priority</span>
          </span>

          <Chevron open={open} />
        </button>

      </div>

      {open && (
        <div className="border-t border-border-dim bg-abyss/80 p-5 animate-fade-in">
          <div className="grid grid-cols-2 gap-4 sm:grid-cols-4">
            <Metric label="ARR exposed" value={formatMoney(problem.commercialExposure)} />
            <Metric
              label="Effort"
              value={problem.incident.estimated_effort_minutes === null ? '—' : `${problem.incident.estimated_effort_minutes}m`}
            />
            <Metric label="Owner" value={problem.incident.current_specialist_id ?? 'Unassigned'} />
            <Metric label="Status" value={problem.incident.status ?? 'Unknown'} />
          </div>

          <div className="mt-5 border-t border-border-dim pt-4">
            <p className="text-xs font-bold uppercase tracking-[0.12em] text-ink-muted">Why this priority</p>
            <div className="mt-3 flex flex-wrap gap-2">
              {problem.signals.map((signal) => (
                <span
                  key={signal.id}
                  className={`rounded-full border ${style.border} px-3 py-1.5 text-xs font-semibold text-ink-secondary`}
                >
                  {signal.label} <strong className={style.text}>+{signal.weight}</strong>
                </span>
              ))}
            </div>
          </div>

          {problem.incident.required_skills.length > 0 && (
            <div className="mt-4 flex flex-wrap items-center gap-2">
              <span className="text-sm text-ink-muted">Skills needed:</span>
              {problem.incident.required_skills.map((skill) => (
                <span key={skill} className="rounded-full bg-deep px-3 py-1 text-sm font-semibold text-ink-secondary">
                  {skill}
                </span>
              ))}
            </div>
          )}

          <div className="mt-5 border-t border-border-dim pt-5">
            <div className="mb-4">
              <p className="text-sm font-bold text-ops-amber">Ask OptiFlow about this problem</p>
              <p className="mt-1 text-sm text-ink-muted">
                Customer, SLA, effort, and required skills are already included.
              </p>
            </div>
            <GoalInput
              compact
              suggestedGoal={suggestedGoal}
              suggestionKey={problem.incident.incident_id}
              selectedProblemCount={1}
            />
          </div>
        </div>
      )}
    </article>
  );
}

function LoadingBoard() {
  return (
    <div className="mx-auto max-w-7xl px-5 py-8 sm:px-8" aria-label="Loading today's operations">
      <div className="h-9 w-56 animate-pulse rounded-lg bg-surface" />
      <div className="mt-7 flex gap-3 overflow-hidden">
        {Array.from({ length: 4 }, (_, index) => (
          <div key={index} className="h-36 min-w-[210px] animate-pulse rounded-2xl bg-deep" />
        ))}
      </div>
      <div className="mt-8 space-y-3">
        {Array.from({ length: 3 }, (_, index) => (
          <div key={index} className="h-24 animate-pulse rounded-2xl bg-deep" />
        ))}
      </div>
    </div>
  );
}

export function TodayDecisionBoard() {
  const [portfolio, setPortfolio] = useState<DemoPortfolio | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [openWorkerId, setOpenWorkerId] = useState<string | null>(null);
  const [openProblemId, setOpenProblemId] = useState<string | null>(null);

  const loadPortfolio = useCallback(async () => {
    setLoading(true);
    try {
      setPortfolio(await api.getDemoPortfolio());
      setError(null);
    } catch (caught: unknown) {
      setError(caught instanceof Error ? caught.message : 'Today\'s live data is unavailable');
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    void loadPortfolio();
    const timer = window.setInterval(() => void loadPortfolio(), 10_000);
    return () => window.clearInterval(timer);
  }, [loadPortfolio]);

  const problems = useMemo(
    () => portfolio ? deriveTodayProblems(portfolio) : [],
    [portfolio],
  );
  const workers = useMemo(
    () => portfolio ? deriveTeamReadiness(portfolio) : [],
    [portfolio],
  );
  const assignedProblemsByWorker = useMemo(() => {
    const result = new Map<string, DemoIncident[]>();
    if (!portfolio) return result;
    const closedStatuses = new Set(['CLOSED', 'RESOLVED', 'CANCELLED']);
    portfolio.incidents.forEach((incident) => {
      const specialistId = incident.current_specialist_id;
      const status = incident.status?.toUpperCase() ?? '';
      if (!specialistId || closedStatuses.has(status)) return;
      const assigned = result.get(specialistId) ?? [];
      assigned.push(incident);
      result.set(specialistId, assigned);
    });
    return result;
  }, [portfolio]);
  const selectedWorker = workers.find(
    (worker) => worker.specialist.specialist_id === openWorkerId,
  ) ?? null;

  if (loading && !portfolio) return <LoadingBoard />;

  if (error && !portfolio) {
    return (
      <div className="mx-auto max-w-7xl px-5 py-12 sm:px-8">
        <div className="flex flex-wrap items-center justify-between gap-4 rounded-2xl border border-ops-rose/30 bg-ops-rose/5 p-6">
          <div>
            <p className="text-base font-extrabold text-ops-rose">Today&apos;s live data did not load.</p>
            <p className="mt-1 text-sm text-ink-muted">{error}</p>
          </div>
          <button
            type="button"
            onClick={() => void loadPortfolio()}
            className="rounded-xl border border-ops-rose/30 px-4 py-2 text-sm font-bold text-ops-rose focus-ring"
          >
            Try again
          </button>
        </div>
      </div>
    );
  }

  if (!portfolio) return null;
  const summary = portfolio.portfolio_summary;

  return (
    <div className="mx-auto max-w-7xl space-y-8 overflow-hidden px-5 py-7 sm:px-8 lg:py-9">
      <header className="flex flex-col justify-between gap-5 lg:flex-row lg:items-end">
        <div>
          <div className="flex items-center gap-2">
            <span className="relative flex h-2.5 w-2.5">
              <span className="absolute inset-0 animate-ping rounded-full bg-ops-emerald opacity-30" />
              <span className="relative h-2.5 w-2.5 rounded-full bg-ops-emerald" />
            </span>
            <p className="text-xs font-bold uppercase tracking-[0.16em] text-ops-emerald">Live · refreshes every 10s</p>
            {(portfolio.degraded || summary.partial) && (
              <span className="rounded-full bg-ops-orange/10 px-2 py-1 text-xs font-bold text-ops-orange">
                Partial data
              </span>
            )}
          </div>
          <h1 className="mt-2 text-3xl font-extrabold tracking-[-0.045em] text-ink-primary sm:text-4xl">
            Today&apos;s operations
          </h1>
        </div>

        <div className="flex items-center gap-2 overflow-x-auto pb-1">
          {[
            [summary.total_active_incidents ?? 0, 'Active'],
            [summary.incidents_near_sla_breach ?? 0, 'Near SLA'],
            [summary.unassigned_incidents ?? 0, 'Unassigned'],
            [`${summary.available_specialists ?? 0}/${summary.total_specialists ?? 0}`, 'Team ready'],
          ].map(([value, label]) => (
            <div key={label} className="min-w-[92px] rounded-xl border border-border-dim bg-abyss px-3 py-2">
              <p className="text-lg font-extrabold text-ink-primary">{value}</p>
              <p className="text-xs text-ink-muted">{label}</p>
            </div>
          ))}
          <button
            type="button"
            onClick={() => void loadPortfolio()}
            disabled={loading}
            aria-label="Refresh live data"
            className="flex h-11 w-11 shrink-0 items-center justify-center rounded-xl border border-border-dim bg-abyss text-ink-muted hover:text-ops-cyan disabled:opacity-40 focus-ring"
          >
            <RefreshIcon spinning={loading} />
          </button>
        </div>
      </header>

      <section aria-labelledby="today-team-heading">
        <div className="flex items-end justify-between gap-4">
          <div>
            <p className="text-xs font-bold uppercase tracking-[0.14em] text-ops-cyan">Team</p>
            <h2 id="today-team-heading" className="mt-1 text-xl font-extrabold text-ink-primary">
              Workers present today
            </h2>
          </div>
          <p className="hidden text-sm text-ink-muted sm:block">Select a worker for details</p>
        </div>

        <div className="-mx-1 mt-4 flex snap-x gap-3 overflow-x-auto px-1 pb-3">
          {workers.map((worker) => (
            <div key={worker.specialist.specialist_id} className="snap-start">
              <WorkerButton
                worker={worker}
                assignedProblems={assignedProblemsByWorker.get(worker.specialist.specialist_id) ?? []}
                open={openWorkerId === worker.specialist.specialist_id}
                onClick={() => setOpenWorkerId((current) => (
                  current === worker.specialist.specialist_id
                    ? null
                    : worker.specialist.specialist_id
                ))}
              />
            </div>
          ))}
        </div>
        {selectedWorker && (
          <WorkerDetail
            worker={selectedWorker}
            assignedProblems={assignedProblemsByWorker.get(selectedWorker.specialist.specialist_id) ?? []}
          />
        )}
      </section>

      <section aria-labelledby="today-problems-heading">
        <div className="flex items-end justify-between gap-4">
          <div>
            <p className="text-xs font-bold uppercase tracking-[0.14em] text-ops-rose">Priority queue</p>
            <h2 id="today-problems-heading" className="mt-1 text-xl font-extrabold text-ink-primary">
              Today&apos;s problems
            </h2>
          </div>
          <p className="hidden text-sm text-ink-muted sm:block">Open a problem to inspect or analyze it</p>
        </div>

        <div className="mt-4 space-y-3">
          {problems.map((problem) => (
            <ProblemRow
              key={problem.incident.incident_id}
              problem={problem}
              open={openProblemId === problem.incident.incident_id}
              onOpen={() => setOpenProblemId((current) => (
                current === problem.incident.incident_id ? null : problem.incident.incident_id
              ))}
            />
          ))}
        </div>
      </section>

    </div>
  );
}
