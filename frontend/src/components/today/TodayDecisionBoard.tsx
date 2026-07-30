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
import type { DemoPortfolio } from '../../types/api';
import { GoalInput } from '../run/GoalInput';

type IconName =
  | 'alert'
  | 'arrow'
  | 'capacity'
  | 'check'
  | 'clock'
  | 'people'
  | 'refresh'
  | 'shield';

const BAND_STYLES: Record<PressureBand, {
  border: string;
  text: string;
  background: string;
  marker: string;
}> = {
  critical: {
    border: 'border-ops-rose/45',
    text: 'text-ops-rose',
    background: 'bg-ops-rose/[0.055]',
    marker: 'bg-ops-rose',
  },
  urgent: {
    border: 'border-ops-orange/40',
    text: 'text-ops-orange',
    background: 'bg-ops-orange/[0.055]',
    marker: 'bg-ops-orange',
  },
  watch: {
    border: 'border-ops-amber/40',
    text: 'text-ops-amber',
    background: 'bg-ops-amber/[0.045]',
    marker: 'bg-ops-amber',
  },
  routine: {
    border: 'border-border-dim',
    text: 'text-ops-cyan',
    background: 'bg-deep/60',
    marker: 'bg-ops-cyan',
  },
};

const READINESS_STYLES = {
  ready: {
    label: 'Ready',
    ring: 'stroke-ops-emerald',
    text: 'text-ops-emerald',
    dot: 'bg-ops-emerald',
  },
  limited: {
    label: 'Limited',
    ring: 'stroke-ops-amber',
    text: 'text-ops-amber',
    dot: 'bg-ops-amber',
  },
  saturated: {
    label: 'Full',
    ring: 'stroke-ops-rose',
    text: 'text-ops-rose',
    dot: 'bg-ops-rose',
  },
  unavailable: {
    label: 'Away',
    ring: 'stroke-ink-muted',
    text: 'text-ink-muted',
    dot: 'bg-ink-muted',
  },
} as const;

const DECISION_PREVIEW = [
  { id: 'goal', label: 'Goal', icon: 'arrow' as IconName },
  { id: 'frame', label: 'Frame', icon: 'capacity' as IconName },
  { id: 'guard', label: 'Guard', icon: 'shield' as IconName },
  { id: 'evidence', label: 'Pull', icon: 'refresh' as IconName },
  { id: 'compare', label: 'Compare', icon: 'people' as IconName },
  { id: 'human', label: 'Choose', icon: 'check' as IconName },
  { id: 'execute', label: 'Act', icon: 'arrow' as IconName },
  { id: 'verify', label: 'Verify', icon: 'shield' as IconName },
];

function Icon({ name, className = 'w-4 h-4' }: { name: IconName; className?: string }) {
  const paths: Record<IconName, React.ReactNode> = {
    alert: (
      <>
        <path d="M12 4 3.8 19h16.4L12 4Z" />
        <path d="M12 9v4.5M12 16.5h.01" />
      </>
    ),
    arrow: (
      <>
        <path d="M5 12h14M14 7l5 5-5 5" />
      </>
    ),
    capacity: (
      <>
        <circle cx="12" cy="12" r="8" />
        <path d="M12 12V7M12 12l4 2" />
      </>
    ),
    check: (
      <>
        <path d="m5 12 4 4L19 6" />
      </>
    ),
    clock: (
      <>
        <circle cx="12" cy="12" r="8" />
        <path d="M12 8v4l3 2" />
      </>
    ),
    people: (
      <>
        <circle cx="9" cy="9" r="3" />
        <path d="M3.5 19c.8-3.2 2.6-5 5.5-5s4.7 1.8 5.5 5" />
        <path d="M15 7.5a2.5 2.5 0 0 1 0 5M16 14c2.3.4 3.7 2.1 4.2 5" />
      </>
    ),
    refresh: (
      <>
        <path d="M19 7v5h-5M5 17v-5h5" />
        <path d="M7.1 7.1A7 7 0 0 1 19 12M5 12a7 7 0 0 0 11.9 4.9" />
      </>
    ),
    shield: (
      <>
        <path d="M12 3 5 6v5c0 4.8 2.8 8 7 10 4.2-2 7-5.2 7-10V6l-7-3Z" />
        <path d="m9 12 2 2 4-4" />
      </>
    ),
  };

  return (
    <svg
      viewBox="0 0 24 24"
      fill="none"
      stroke="currentColor"
      strokeWidth="1.7"
      strokeLinecap="round"
      strokeLinejoin="round"
      className={className}
      aria-hidden="true"
    >
      {paths[name]}
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
  if (value === null) return 'Value unavailable';
  if (value >= 1_000_000) return `$${(value / 1_000_000).toFixed(1)}m`;
  if (value >= 1_000) return `$${Math.round(value / 1_000)}k`;
  return `$${Math.round(value)}`;
}

function WorkerCapacityRing({ worker }: { worker: WorkerReadiness }) {
  const style = READINESS_STYLES[worker.state];
  const capacity = Math.max(1, worker.specialist.capacity ?? 0);
  const currentPercentage = Math.min(
    100,
    ((worker.specialist.current_workload ?? 0) / capacity) * 100,
  );
  const reservedPercentage = Math.min(100 - currentPercentage, (
    worker.reservedCapacity / capacity
  ) * 100);

  return (
    <div className="relative w-[74px] h-[74px] shrink-0" aria-hidden="true">
      <svg viewBox="0 0 42 42" className="absolute inset-0 w-full h-full -rotate-90">
        <circle
          cx="21"
          cy="21"
          r="17"
          pathLength="100"
          fill="none"
          strokeWidth="3"
          className="stroke-surface"
        />
        <circle
          cx="21"
          cy="21"
          r="17"
          pathLength="100"
          fill="none"
          strokeWidth="3"
          strokeLinecap="round"
          strokeDasharray={`${Math.max(1, currentPercentage)} 100`}
          className={style.ring}
        />
        {reservedPercentage > 0 && (
          <circle
            cx="21"
            cy="21"
            r="17"
            pathLength="100"
            fill="none"
            strokeWidth="3"
            strokeLinecap="round"
            strokeDasharray={`${reservedPercentage} ${100 - reservedPercentage}`}
            strokeDashoffset={-currentPercentage}
            className="stroke-ops-violet"
          />
        )}
      </svg>
      <div className="absolute inset-[9px] rounded-full bg-abyss border border-border-dim flex flex-col items-center justify-center shadow-card">
        <span className="text-[13px] font-extrabold tracking-[-0.04em] text-ink-primary">
          {initials(worker.specialist.specialist_name)}
        </span>
        <span className={`text-[8px] font-mono font-bold ${style.text}`}>
          {worker.remainingCapacity} free
        </span>
      </div>
    </div>
  );
}

function WorkerCard({
  worker,
  selected,
  onSelect,
}: {
  worker: WorkerReadiness;
  selected: boolean;
  onSelect: () => void;
}) {
  const style = READINESS_STYLES[worker.state];

  return (
    <button
      type="button"
      onClick={onSelect}
      aria-pressed={selected}
      className={`min-w-[238px] max-w-[238px] rounded-2xl border p-3.5 text-left transition-all focus-ring ${
        selected
          ? 'border-ops-cyan bg-ops-cyan/[0.055] shadow-card -translate-y-0.5'
          : 'border-border-dim bg-abyss hover:border-border-base hover:-translate-y-0.5'
      }`}
    >
      <div className="flex items-center gap-3">
        <WorkerCapacityRing worker={worker} />
        <div className="min-w-0 flex-1">
          <div className="flex items-center gap-2">
            <span className={`w-1.5 h-1.5 rounded-full ${style.dot}`} />
            <span className={`text-[8px] font-mono font-semibold uppercase tracking-[0.12em] ${style.text}`}>
              {style.label}
            </span>
          </div>
          <p className="text-xs font-extrabold text-ink-primary truncate mt-1.5">
            {worker.specialist.specialist_name}
          </p>
          <div className="flex items-end gap-1 mt-2">
            <span className={`text-xl font-extrabold tracking-[-0.05em] ${style.text}`}>
              {worker.score}
            </span>
            <span className="text-[8px] font-mono uppercase text-ink-muted pb-0.5">
              readiness
            </span>
          </div>
        </div>
      </div>
      <div className="grid grid-cols-3 gap-1.5 mt-3">
        <div className="rounded-lg bg-deep px-2 py-1.5 text-center">
          <p className="text-[10px] font-bold text-ink-primary">{worker.usedCapacity}</p>
          <p className="text-[7px] font-mono uppercase text-ink-muted">used</p>
        </div>
        <div className="rounded-lg bg-ops-violet/[0.07] px-2 py-1.5 text-center">
          <p className="text-[10px] font-bold text-ops-violet">{worker.reservedCapacity}</p>
          <p className="text-[7px] font-mono uppercase text-ink-muted">reserved</p>
        </div>
        <div className="rounded-lg bg-deep px-2 py-1.5 text-center">
          <p className="text-[10px] font-bold text-ink-primary">{worker.utilisation}%</p>
          <p className="text-[7px] font-mono uppercase text-ink-muted">utilised</p>
        </div>
      </div>
    </button>
  );
}

function WorkerDetail({ worker }: { worker: WorkerReadiness }) {
  const style = READINESS_STYLES[worker.state];

  return (
    <div className="rounded-2xl border border-ops-cyan/25 bg-ops-cyan/[0.035] p-4 animate-fade-in">
      <div className="flex flex-wrap items-start justify-between gap-3">
        <div>
          <p className="text-[8px] font-mono uppercase tracking-[0.16em] text-ops-cyan">
            Worker evidence
          </p>
          <h3 className="text-sm font-extrabold text-ink-primary mt-1">
            {worker.specialist.specialist_name}
          </h3>
        </div>
        <span className={`rounded-full bg-abyss border border-border-dim px-2.5 py-1 text-[8px] font-mono font-semibold ${style.text}`}>
          {worker.score}/100 readiness
        </span>
      </div>
      <div className="grid sm:grid-cols-[1fr_auto] gap-4 mt-4">
        <div className="flex flex-wrap gap-1.5">
          {worker.specialist.skills.map((skill) => (
            <span
              key={skill}
              className="rounded-full border border-border-dim bg-abyss px-2.5 py-1 text-[8px] font-medium text-ink-secondary"
            >
              {skill}
            </span>
          ))}
        </div>
        <ul className="space-y-1">
          {worker.reasons.map((reason) => (
            <li key={reason} className="flex items-center gap-2 text-[9px] text-ink-secondary">
              <span className={`w-1 h-1 rounded-full ${style.dot}`} />
              {reason}
            </li>
          ))}
        </ul>
      </div>
    </div>
  );
}

function ProblemCard({
  problem,
  selected,
  explained,
  onToggle,
  onExplain,
}: {
  problem: TodayProblem;
  selected: boolean;
  explained: boolean;
  onToggle: () => void;
  onExplain: () => void;
}) {
  const style = BAND_STYLES[problem.band];
  const title = problem.incident.title ?? problem.incident.summary ?? 'Untitled incident';

  return (
    <article className={`relative rounded-2xl border overflow-hidden transition-all ${style.border} ${style.background} ${
      selected ? 'shadow-card ring-2 ring-ops-cyan/20 -translate-y-0.5' : ''
    }`}>
      <div className={`absolute left-0 top-0 bottom-0 w-1 ${style.marker}`} />
      <div className="p-4 pl-5">
        <div className="flex items-start justify-between gap-3">
          <div className="flex items-center gap-3 min-w-0">
            <span className={`w-9 h-9 rounded-xl border ${style.border} bg-abyss flex items-center justify-center text-base font-extrabold ${style.text}`}>
              {problem.rank}
            </span>
            <div className="min-w-0">
              <p className={`text-[8px] font-mono font-semibold uppercase tracking-[0.14em] ${style.text}`}>
                {problem.band} pressure
              </p>
              <h3 className="text-xs font-extrabold text-ink-primary truncate mt-1">
                {title}
              </h3>
            </div>
          </div>
          <button
            type="button"
            onClick={onToggle}
            aria-pressed={selected}
            className={`shrink-0 w-8 h-8 rounded-full border flex items-center justify-center transition-colors focus-ring ${
              selected
                ? 'border-ops-cyan bg-ops-cyan text-white'
                : 'border-border-base bg-abyss text-ink-muted hover:text-ops-cyan'
            }`}
            aria-label={`${selected ? 'Remove' : 'Add'} ${title} ${selected ? 'from' : 'to'} the objective`}
          >
            {selected ? <Icon name="check" /> : <span className="text-lg leading-none">+</span>}
          </button>
        </div>

        <div className="grid grid-cols-2 gap-x-3 gap-y-2 mt-4">
          <div>
            <p className="text-[7px] font-mono uppercase tracking-[0.13em] text-ink-muted">Customer</p>
            <p className="text-[10px] font-bold text-ink-secondary truncate mt-1">
              {problem.customer?.customer_name ?? problem.incident.customer_id}
            </p>
          </div>
          <div>
            <p className="text-[7px] font-mono uppercase tracking-[0.13em] text-ink-muted">SLA clock</p>
            <p className={`text-[10px] font-bold truncate mt-1 ${style.text}`}>
              {problem.deadlineLabel}
            </p>
          </div>
          <div>
            <p className="text-[7px] font-mono uppercase tracking-[0.13em] text-ink-muted">Exposure</p>
            <p className="text-[10px] font-bold text-ink-secondary mt-1">
              {formatMoney(problem.commercialExposure)}
            </p>
          </div>
          <div>
            <p className="text-[7px] font-mono uppercase tracking-[0.13em] text-ink-muted">Owner</p>
            <p className={`text-[10px] font-bold truncate mt-1 ${
              problem.incident.current_specialist_id ? 'text-ink-secondary' : 'text-ops-rose'
            }`}>
              {problem.incident.current_specialist_id ?? 'Unassigned'}
            </p>
          </div>
        </div>

        <div className="flex items-center justify-between gap-3 mt-4 pt-3 border-t border-border-dim">
          <p className="min-w-0 text-[9px] text-ink-muted truncate">
            {problem.topReasons.join(' + ') || 'No strong pressure signal'}
          </p>
          <button
            type="button"
            onClick={onExplain}
            className={`shrink-0 text-[9px] font-bold hover:underline focus-ring rounded ${style.text}`}
          >
            Why #{problem.rank}?
          </button>
        </div>
      </div>

      {explained && (
        <div className="border-t border-border-dim bg-abyss/80 px-5 py-4 animate-fade-in">
          <div className="flex items-center justify-between gap-3">
            <p className="text-[8px] font-mono uppercase tracking-[0.14em] text-ink-muted">
              Live pressure evidence
            </p>
            <span className={`text-[9px] font-mono font-bold ${style.text}`}>
              score {problem.score}
            </span>
          </div>
          <ul className="space-y-2 mt-3">
            {problem.signals.map((signal) => (
              <li key={signal.id} className="grid grid-cols-[auto_1fr_auto] gap-2 items-start">
                <span className={`w-1.5 h-1.5 rounded-full mt-1 ${style.marker}`} />
                <div>
                  <p className="text-[9px] font-bold text-ink-secondary">{signal.label}</p>
                  <p className="text-[8px] leading-relaxed text-ink-muted mt-0.5">{signal.detail}</p>
                </div>
                <span className="text-[8px] font-mono text-ink-muted">+{signal.weight}</span>
              </li>
            ))}
          </ul>
          <p className="text-[8px] leading-relaxed text-ink-muted mt-3 pt-3 border-t border-border-dim">
            This is a transparent UI pressure order from current facts, not an optimiser recommendation.
          </p>
        </div>
      )}
    </article>
  );
}

function DecisionMapPreview() {
  return (
    <section className="rounded-[1.5rem] border border-border-dim bg-ink-primary text-white p-5 sm:p-6 overflow-hidden">
      <div className="flex flex-wrap items-end justify-between gap-3">
        <div>
          <p className="text-[8px] font-mono uppercase tracking-[0.18em] text-[#ff8a64]">
            What opens next
          </p>
          <h2 className="text-lg font-extrabold tracking-[-0.035em] mt-1.5">
            A live decision map, not a report.
          </h2>
        </div>
        <span className="rounded-full border border-white/15 px-2.5 py-1 text-[8px] font-mono text-white/55">
          Click every node for evidence
        </span>
      </div>

      <div className="overflow-x-auto -mx-2 px-2 pb-2 mt-6">
        <div className="relative min-w-[760px] grid grid-cols-8 gap-4">
          <div className="absolute left-[5%] right-[5%] top-6 h-px bg-white/15" />
          <div className="absolute left-[5%] right-[82%] top-6 h-px bg-[#ff8a64]" />
          {DECISION_PREVIEW.map((node, index) => (
            <div key={node.id} className="relative z-10 flex flex-col items-center text-center">
              <div className="relative w-12 h-12">
                {index === 0 && (
                  <span className="absolute inset-[-5px] rounded-full border border-dashed border-[#ff8a64]/70 animate-spin-slow" />
                )}
                <span className={`absolute inset-0 rounded-full border flex items-center justify-center ${
                  index === 0
                    ? 'border-[#ff8a64] bg-[#ff8a64] text-white'
                    : index === 5
                      ? 'border-[#ff8a64]/50 bg-[#ff8a64]/10 text-[#ff8a64]'
                      : 'border-white/15 bg-white/[0.055] text-white/45'
                }`}>
                  <Icon name={node.icon} />
                </span>
              </div>
              <span className={`text-[8px] font-mono font-semibold uppercase tracking-[0.1em] mt-3 ${
                index === 0 ? 'text-[#ff8a64]' : 'text-white/45'
              }`}>
                {node.label}
              </span>
            </div>
          ))}
        </div>
      </div>
    </section>
  );
}

export function TodayDecisionBoard() {
  const [portfolio, setPortfolio] = useState<DemoPortfolio | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [selectedWorkerId, setSelectedWorkerId] = useState<string | null>(null);
  const [selectedProblemIds, setSelectedProblemIds] = useState<string[]>([]);
  const [explainedProblemId, setExplainedProblemId] = useState<string | null>(null);

  const loadPortfolio = useCallback(async () => {
    setLoading(true);
    try {
      setPortfolio(await api.getDemoPortfolio());
      setError(null);
    } catch (caught: unknown) {
      setError(caught instanceof Error ? caught.message : 'Today\'s portfolio is unavailable');
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    void loadPortfolio();
  }, [loadPortfolio]);

  const problems = useMemo(
    () => portfolio ? deriveTodayProblems(portfolio) : [],
    [portfolio],
  );
  const workers = useMemo(
    () => portfolio ? deriveTeamReadiness(portfolio) : [],
    [portfolio],
  );
  const selectedProblems = useMemo(() => {
    const explicit = problems.filter((problem) => (
      selectedProblemIds.includes(problem.incident.incident_id)
    ));
    return explicit.length > 0 ? explicit : problems.slice(0, 3);
  }, [problems, selectedProblemIds]);
  const suggestedGoal = useMemo(
    () => buildGoalFromProblems(selectedProblems),
    [selectedProblems],
  );
  const suggestionKey = selectedProblems
    .map((problem) => problem.incident.incident_id)
    .join('|') || 'portfolio';
  const selectedWorker = workers.find(
    (worker) => worker.specialist.specialist_id === selectedWorkerId,
  ) ?? null;

  if (loading && !portfolio) {
    return (
      <div className="max-w-7xl mx-auto px-5 sm:px-8 py-8" aria-label="Loading today's decision board">
        <div className="h-8 w-64 rounded-lg bg-surface animate-pulse" />
        <div className="flex gap-3 overflow-hidden mt-7">
          {Array.from({ length: 4 }, (_, index) => (
            <div key={index} className="h-44 min-w-[238px] rounded-2xl bg-deep animate-pulse" />
          ))}
        </div>
        <div className="grid md:grid-cols-2 xl:grid-cols-3 gap-3 mt-8">
          {Array.from({ length: 3 }, (_, index) => (
            <div key={index} className="h-56 rounded-2xl bg-deep animate-pulse" />
          ))}
        </div>
      </div>
    );
  }

  if (error && !portfolio) {
    return (
      <div className="max-w-7xl mx-auto px-5 sm:px-8 py-12">
        <div className="rounded-2xl border border-ops-rose/30 bg-ops-rose/5 p-6 flex flex-wrap items-center justify-between gap-4">
          <div className="flex items-center gap-3">
            <span className="w-10 h-10 rounded-full bg-ops-rose/10 text-ops-rose flex items-center justify-center">
              <Icon name="alert" />
            </span>
            <div>
              <p className="text-sm font-extrabold text-ops-rose">Today&apos;s evidence did not load.</p>
              <p className="text-[10px] text-ink-muted mt-1">{error}</p>
            </div>
          </div>
          <button
            type="button"
            onClick={() => void loadPortfolio()}
            className="rounded-xl border border-ops-rose/30 px-4 py-2 text-xs font-bold text-ops-rose hover:bg-ops-rose/5 focus-ring"
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
    <div className="max-w-7xl mx-auto px-5 sm:px-8 py-7 lg:py-9 space-y-7">
      <header className="flex flex-col lg:flex-row lg:items-end justify-between gap-5">
        <div>
          <div className="flex items-center gap-2">
            <span className="relative flex w-2 h-2">
              <span className="absolute inset-0 rounded-full bg-ops-emerald animate-ping opacity-30" />
              <span className="relative w-2 h-2 rounded-full bg-ops-emerald" />
            </span>
            <p className="text-[8px] font-mono font-semibold uppercase tracking-[0.2em] text-ops-emerald">
              Live operational picture
            </p>
            {(portfolio.degraded || summary.partial) && (
              <span className="rounded-full bg-ops-orange/10 px-2 py-1 text-[7px] font-mono uppercase text-ops-orange">
                Partial evidence
              </span>
            )}
          </div>
          <h1 className="text-[clamp(2rem,5vw,4.6rem)] font-extrabold leading-[0.95] tracking-[-0.065em] mt-3">
            See today. <span className="text-ops-amber">Choose the move.</span>
          </h1>
        </div>
        <div className="flex items-center gap-2 overflow-x-auto pb-1">
          {[
            [`${summary.total_active_incidents ?? 0}`, 'active'],
            [`${summary.incidents_near_sla_breach ?? 0}`, 'near SLA'],
            [`${summary.unassigned_incidents ?? 0}`, 'unassigned'],
            [`${summary.available_specialists ?? 0}/${summary.total_specialists ?? 0}`, 'team ready'],
          ].map(([value, label]) => (
            <div key={label} className="min-w-[82px] rounded-xl border border-border-dim bg-abyss px-3 py-2.5">
              <p className="text-base font-extrabold tracking-[-0.04em] text-ink-primary">{value}</p>
              <p className="text-[7px] font-mono uppercase tracking-[0.12em] text-ink-muted mt-0.5">{label}</p>
            </div>
          ))}
          <button
            type="button"
            onClick={() => void loadPortfolio()}
            disabled={loading}
            className="w-10 h-10 shrink-0 rounded-full border border-border-dim bg-abyss text-ink-muted hover:text-ops-cyan disabled:opacity-40 flex items-center justify-center focus-ring"
            aria-label="Refresh today's evidence"
          >
            <Icon name="refresh" className={`w-4 h-4 ${loading ? 'animate-spin' : ''}`} />
          </button>
        </div>
      </header>

      <section aria-labelledby="team-today-title">
        <div className="flex flex-wrap items-end justify-between gap-3">
          <div>
            <div className="flex items-center gap-2">
              <span className="w-7 h-7 rounded-lg bg-ops-cyan/10 text-ops-cyan flex items-center justify-center">
                <Icon name="people" />
              </span>
              <div>
                <p className="text-[8px] font-mono uppercase tracking-[0.17em] text-ops-cyan">
                  Team orbit
                </p>
                <h2 id="team-today-title" className="text-lg font-extrabold tracking-[-0.035em]">
                  Workforce present today
                </h2>
              </div>
            </div>
          </div>
          <div className="flex items-center gap-3 text-[8px] font-mono uppercase text-ink-muted">
            <span className="flex items-center gap-1.5">
              <span className="w-2 h-2 rounded-full bg-ops-emerald" /> capacity
            </span>
            <span className="flex items-center gap-1.5">
              <span className="w-2 h-2 rounded-full bg-ops-violet" /> reserved
            </span>
          </div>
        </div>

        <div className="flex gap-3 overflow-x-auto snap-x pb-3 -mx-1 px-1 mt-4">
          {workers.map((worker) => (
            <div key={worker.specialist.specialist_id} className="snap-start">
              <WorkerCard
                worker={worker}
                selected={selectedWorkerId === worker.specialist.specialist_id}
                onSelect={() => setSelectedWorkerId((current) => (
                  current === worker.specialist.specialist_id
                    ? null
                    : worker.specialist.specialist_id
                ))}
              />
            </div>
          ))}
        </div>
        {selectedWorker && <WorkerDetail worker={selectedWorker} />}
      </section>

      <section aria-labelledby="today-problems-title">
        <div className="flex flex-wrap items-end justify-between gap-3">
          <div className="flex items-center gap-2">
            <span className="w-7 h-7 rounded-lg bg-ops-rose/10 text-ops-rose flex items-center justify-center">
              <Icon name="alert" />
            </span>
            <div>
              <p className="text-[8px] font-mono uppercase tracking-[0.17em] text-ops-rose">
                Live pressure order
              </p>
              <h2 id="today-problems-title" className="text-lg font-extrabold tracking-[-0.035em]">
                Today&apos;s problems
              </h2>
            </div>
          </div>
          <p className="text-[9px] text-ink-muted">
            Select cards to shape the objective · open Why for evidence
          </p>
        </div>

        {problems.length > 0 ? (
          <div className="grid md:grid-cols-2 xl:grid-cols-3 gap-3 mt-4">
            {problems.map((problem) => (
              <ProblemCard
                key={problem.incident.incident_id}
                problem={problem}
                selected={selectedProblemIds.includes(problem.incident.incident_id)}
                explained={explainedProblemId === problem.incident.incident_id}
                onToggle={() => setSelectedProblemIds((current) => (
                  current.includes(problem.incident.incident_id)
                    ? current.filter((id) => id !== problem.incident.incident_id)
                    : [...current, problem.incident.incident_id]
                ))}
                onExplain={() => setExplainedProblemId((current) => (
                  current === problem.incident.incident_id
                    ? null
                    : problem.incident.incident_id
                ))}
              />
            ))}
          </div>
        ) : (
          <div className="rounded-2xl border border-ops-emerald/25 bg-ops-emerald/5 p-6 mt-4 flex items-center gap-3">
            <span className="w-10 h-10 rounded-full bg-ops-emerald/10 text-ops-emerald flex items-center justify-center">
              <Icon name="check" />
            </span>
            <p className="text-sm font-bold text-ink-primary">No active incident pressure is currently reported.</p>
          </div>
        )}
      </section>

      <section className="grid lg:grid-cols-[minmax(0,1.15fr)_minmax(320px,0.85fr)] gap-4 items-start">
        <article className="rounded-[1.5rem] border border-border-base bg-abyss shadow-card overflow-hidden">
          <div className="h-1 bg-ops-amber" />
          <div className="p-5 sm:p-6">
            <div className="flex flex-wrap items-center justify-between gap-3 mb-4">
              <div>
                <p className="text-[8px] font-mono uppercase tracking-[0.17em] text-ops-amber">
                  Human direction
                </p>
                <h2 className="text-lg font-extrabold tracking-[-0.035em] mt-1">
                  Start suggested—or change it.
                </h2>
              </div>
              <span className="flex items-center gap-1.5 text-[8px] font-mono uppercase text-ops-emerald">
                <Icon name="shield" className="w-3.5 h-3.5" />
                approval required
              </span>
            </div>
            <GoalInput
              compact
              suggestedGoal={suggestedGoal}
              suggestionKey={suggestionKey}
              selectedProblemCount={selectedProblems.length}
            />
          </div>
        </article>

        <DecisionMapPreview />
      </section>
    </div>
  );
}
