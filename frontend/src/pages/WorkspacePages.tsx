import { useEffect, useMemo, useState } from 'react';
import { Link, useNavigate } from 'react-router-dom';
import { api } from '../api/client';
import type { RecentRun, RunStatus, RunSummary } from '../types/api';

type WorkspacePageProps = {
  eyebrow: string;
  title: string;
  description: string;
  purpose: string;
  capabilities: string[];
};

type HistoryView = 'all' | 'attention' | 'moving' | 'closed';

type HistoryRun = RecentRun & {
  summary: RunSummary | null;
  statusError: boolean;
};

const STATUS_GUIDE: Record<RunStatus, {
  label: string;
  group: Exclude<HistoryView, 'all'>;
  next: string;
  explanation: string;
  badge: string;
  marker: string;
}> = {
  RECEIVED: {
    label: 'Route received',
    group: 'moving',
    next: 'Open the route and check whether interpretation has started.',
    explanation: 'Core registered the goal and created its audit identity.',
    badge: 'border-border-base bg-surface text-ink-secondary',
    marker: 'bg-ink-muted',
  },
  RUNNING: {
    label: 'Engines working',
    group: 'moving',
    next: 'Watch the cards arrive; no decision is required yet.',
    explanation: 'OptiFlow is interpreting, checking evidence, or comparing plans.',
    badge: 'border-ops-cyan/25 bg-ops-cyan/10 text-ops-cyan',
    marker: 'bg-ops-cyan',
  },
  WAITING_FOR_CLARIFICATION: {
    label: 'Answer needed',
    group: 'attention',
    next: 'Open the route and answer the unresolved policy question.',
    explanation: 'The system stopped instead of making an important assumption.',
    badge: 'border-ops-orange/30 bg-ops-orange/10 text-ops-orange',
    marker: 'bg-ops-orange',
  },
  WAITING_FOR_APPROVAL: {
    label: 'Decision needed',
    group: 'attention',
    next: 'Compare all plans and approve only the trade-off you accept.',
    explanation: 'Planning is complete and operational writes remain blocked.',
    badge: 'border-ops-amber/30 bg-ops-amber/10 text-ops-amber',
    marker: 'bg-ops-amber',
  },
  EXECUTING: {
    label: 'Applying safely',
    group: 'moving',
    next: 'Open the execution relay to watch each verified hand-off.',
    explanation: 'The approved plan is crossing reversible service boundaries.',
    badge: 'border-ops-orange/30 bg-ops-orange/10 text-ops-orange',
    marker: 'bg-ops-orange',
  },
  REPLANNING: {
    label: 'Finding a safer route',
    group: 'moving',
    next: 'Review which pairing was excluded and wait for replacement plans.',
    explanation: 'A rejection or timeout became a new optimisation constraint.',
    badge: 'border-ops-violet/30 bg-ops-violet/10 text-ops-violet',
    marker: 'bg-ops-violet',
  },
  EXECUTED: {
    label: 'Writes recorded',
    group: 'moving',
    next: 'Wait for Core to close the audit record.',
    explanation: 'The SAGA completed and the final route record is being closed.',
    badge: 'border-ops-cyan/25 bg-ops-cyan/10 text-ops-cyan',
    marker: 'bg-ops-cyan',
  },
  FAILED_SAGA: {
    label: 'Execution review',
    group: 'attention',
    next: 'Inspect the failed boundary and compensation evidence before retrying.',
    explanation: 'The operational transaction stopped before successful completion.',
    badge: 'border-ops-rose/30 bg-ops-rose/10 text-ops-rose',
    marker: 'bg-ops-rose',
  },
  COMPLETED: {
    label: 'Route closed',
    group: 'closed',
    next: 'Reopen the journey to review evidence, trade-offs, and receipts.',
    explanation: 'Core marked the decision route complete and closed its audit record.',
    badge: 'border-ops-emerald/25 bg-ops-emerald/10 text-ops-emerald',
    marker: 'bg-ops-emerald',
  },
  FAILED: {
    label: 'Safely stopped',
    group: 'closed',
    next: 'Review the failure context before deciding whether to try again.',
    explanation: 'The route stopped without claiming a completed decision.',
    badge: 'border-ops-rose/30 bg-ops-rose/10 text-ops-rose',
    marker: 'bg-ops-rose',
  },
  CANCELLED: {
    label: 'Cancelled',
    group: 'closed',
    next: 'Review the record or reuse the goal to start a fresh route.',
    explanation: 'The decision route was intentionally ended.',
    badge: 'border-border-base bg-surface text-ink-secondary',
    marker: 'bg-ink-muted',
  },
};

const HISTORY_VIEWS: { id: HistoryView; label: string; description: string }[] = [
  { id: 'all', label: 'All routes', description: 'Every route saved by this browser' },
  { id: 'attention', label: 'Needs me', description: 'Clarification, approval, or execution review' },
  { id: 'moving', label: 'Moving', description: 'Core is still advancing the route' },
  { id: 'closed', label: 'Closed', description: 'Completed, failed, or cancelled records' },
];

function readHistory(): HistoryRun[] {
  try {
    const saved = JSON.parse(localStorage.getItem('optiflow_runs') ?? '[]') as RecentRun[];
    return saved.map((run) => ({ ...run, summary: null, statusError: false }));
  } catch {
    return [];
  }
}

function formatRunDate(value: string): string {
  const parsed = new Date(value);
  if (Number.isNaN(parsed.getTime())) return 'Date not recorded';
  return new Intl.DateTimeFormat('en-US', {
    month: 'short',
    day: 'numeric',
    hour: '2-digit',
    minute: '2-digit',
  }).format(parsed);
}

function WorkspacePage({
  eyebrow,
  title,
  description,
  purpose,
  capabilities,
}: WorkspacePageProps) {
  return (
    <div className="min-h-full paper-noise">
      <section className="max-w-6xl mx-auto px-5 sm:px-8 py-12 lg:py-20">
        <div className="grid lg:grid-cols-[minmax(0,1fr)_320px] gap-8 lg:gap-16 items-start">
          <div>
            <p className="text-[10px] font-mono font-semibold uppercase tracking-[0.2em] text-ops-cyan">
              {eyebrow}
            </p>
            <h1 className="max-w-3xl text-4xl sm:text-6xl font-extrabold tracking-[-0.06em] leading-[1.02] mt-4">
              {title}
            </h1>
            <p className="max-w-2xl text-base sm:text-lg leading-relaxed text-ink-secondary mt-6">
              {description}
            </p>
          </div>

          <aside className="rounded-[1.75rem] border border-border-base bg-abyss shadow-card overflow-hidden">
            <div className="h-1.5 bg-ops-cyan" />
            <div className="p-6">
              <p className="text-[9px] font-mono uppercase tracking-[0.18em] text-ink-muted">
                Workspace purpose
              </p>
              <p className="text-xl font-extrabold tracking-[-0.04em] text-ink-primary mt-3">
                {purpose}
              </p>
              <ul className="mt-5 space-y-3">
                {capabilities.map((capability) => (
                  <li key={capability} className="flex gap-3 text-sm leading-relaxed text-ink-secondary">
                    <span className="mt-2 w-1.5 h-1.5 shrink-0 rounded-full bg-ops-cyan" />
                    <span>{capability}</span>
                  </li>
                ))}
              </ul>
              <div className="mt-6 pt-5 border-t border-border-dim flex items-center gap-2 text-[10px] font-mono uppercase tracking-[0.14em] text-ops-emerald">
                <span className="w-2 h-2 rounded-full bg-ops-emerald" />
                Connected to Core
              </div>
            </div>
          </aside>
        </div>
      </section>
    </div>
  );
}

export function RunHistoryPage() {
  const navigate = useNavigate();
  const [runs, setRuns] = useState<HistoryRun[]>(readHistory);
  const [activeView, setActiveView] = useState<HistoryView>('all');
  const [refreshing, setRefreshing] = useState(runs.length > 0);

  useEffect(() => {
    if (runs.length === 0) {
      setRefreshing(false);
      return;
    }

    let cancelled = false;
    const refresh = async () => {
      const refreshed = await Promise.all(runs.map(async (run): Promise<HistoryRun> => {
        try {
          const summary = await api.getRunStatus(run.run_id);
          return {
            ...run,
            status: summary.status,
            summary,
            statusError: false,
          };
        } catch {
          return { ...run, summary: null, statusError: true };
        }
      }));

      if (cancelled) return;
      setRuns(refreshed);
      setRefreshing(false);
      try {
        const saved: RecentRun[] = refreshed.map((run) => ({
          run_id: run.run_id,
          goal_text: run.goal_text,
          status: run.status,
          created_at: run.created_at,
        }));
        localStorage.setItem('optiflow_runs', JSON.stringify(saved));
      } catch {
        // Browser history remains useful even when persistence is unavailable.
      }
    };

    void refresh();
    return () => {
      cancelled = true;
    };
    // Refresh the saved snapshot once when the page opens.
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  const counts = useMemo(() => ({
    all: runs.length,
    attention: runs.filter((run) => STATUS_GUIDE[run.status].group === 'attention').length,
    moving: runs.filter((run) => STATUS_GUIDE[run.status].group === 'moving').length,
    closed: runs.filter((run) => STATUS_GUIDE[run.status].group === 'closed').length,
  }), [runs]);

  const visibleRuns = useMemo(
    () => activeView === 'all'
      ? runs
      : runs.filter((run) => STATUS_GUIDE[run.status].group === activeView),
    [activeView, runs],
  );

  const reuseGoal = (goal: string) => {
    try {
      sessionStorage.setItem('optiflow_goal_draft', goal);
    } catch {
      // Navigation still works; the user can copy from the history card.
    }
    navigate('/');
  };

  return (
    <div className="min-h-full paper-noise">
      <section className="border-b border-border-dim bg-abyss">
        <div className="max-w-7xl mx-auto px-5 sm:px-8 py-10 lg:py-14">
          <div className="grid lg:grid-cols-[minmax(0,1fr)_340px] gap-8 items-end">
            <div>
              <p className="text-[9px] font-mono font-semibold uppercase tracking-[0.2em] text-ops-cyan">
                Decision memory
              </p>
              <h1 className="max-w-4xl text-4xl sm:text-6xl font-extrabold tracking-[-0.06em] leading-[0.98] mt-4">
                Every route leaves a
                <span className="block text-ops-cyan">teachable trail.</span>
              </h1>
              <p className="max-w-2xl text-sm sm:text-base leading-relaxed text-ink-secondary mt-5">
                Resume unfinished work, reopen the exact evidence and trade-offs, or reuse an earlier
                goal with today&apos;s portfolio state.
              </p>
            </div>
            <aside className="rounded-2xl border border-border-dim bg-deep p-5">
              <p className="text-[8px] font-mono font-semibold uppercase tracking-[0.16em] text-ink-muted">
                Current history scope
              </p>
              <p className="text-sm font-bold text-ink-primary mt-2">Last 10 routes from this browser</p>
              <p className="text-[10px] leading-relaxed text-ink-muted mt-2">
                Statuses refresh from Core. A backend run-list endpoint is still needed for shared,
                cross-device team history.
              </p>
              <div className="flex items-center gap-2 mt-4 pt-4 border-t border-border-dim text-[9px] font-mono uppercase tracking-[0.12em] text-ops-emerald">
                <span className={`w-2 h-2 rounded-full bg-ops-emerald ${refreshing ? 'animate-pulse' : ''}`} />
                {refreshing ? 'Refreshing from Core' : 'Core status checked'}
              </div>
            </aside>
          </div>
        </div>
      </section>

      <section className="max-w-7xl mx-auto px-5 sm:px-8 py-8 lg:py-10">
        <div className="grid grid-cols-2 lg:grid-cols-4 gap-3" role="tablist" aria-label="History views">
          {HISTORY_VIEWS.map((view) => {
            const active = activeView === view.id;
            return (
              <button
                key={view.id}
                type="button"
                role="tab"
                aria-selected={active}
                onClick={() => setActiveView(view.id)}
                className={`rounded-2xl border p-4 text-left transition-all focus-ring ${
                  active
                    ? 'border-ops-cyan bg-ops-cyan/[0.06] shadow-card'
                    : 'border-border-dim bg-abyss hover:border-border-base'
                }`}
              >
                <div className="flex items-center justify-between gap-3">
                  <span className={`text-[10px] font-bold ${active ? 'text-ops-cyan' : 'text-ink-secondary'}`}>
                    {view.label}
                  </span>
                  <span className="text-xl font-extrabold text-ink-primary">{counts[view.id]}</span>
                </div>
                <p className="hidden sm:block text-[9px] leading-relaxed text-ink-muted mt-2">
                  {view.description}
                </p>
              </button>
            );
          })}
        </div>

        {visibleRuns.length === 0 ? (
          <div className="mt-6 rounded-[1.75rem] border border-dashed border-border-base bg-abyss px-6 py-16 text-center">
            <p className="text-[9px] font-mono uppercase tracking-[0.18em] text-ink-muted">
              {runs.length === 0 ? 'No decision routes yet' : `No ${HISTORY_VIEWS.find((view) => view.id === activeView)?.label.toLowerCase()}`}
            </p>
            <h2 className="text-xl font-extrabold tracking-[-0.035em] text-ink-primary mt-3">
              {runs.length === 0 ? 'Your first trail begins with today’s goal.' : 'Nothing is waiting in this view.'}
            </h2>
            <p className="text-xs leading-relaxed text-ink-muted mt-2">
              {runs.length === 0
                ? 'State the outcome, boundary, and timeframe. OptiFlow will preserve every card here.'
                : 'Choose another history view to inspect the routes saved in this browser.'}
            </p>
            {runs.length === 0 && (
              <Link
                to="/"
                className="inline-flex mt-5 rounded-xl bg-ink-primary px-5 py-3 text-xs font-bold text-white hover:bg-ops-cyan focus-ring"
              >
                Set today&apos;s goal
              </Link>
            )}
          </div>
        ) : (
          <div className="relative mt-7">
            <div className="absolute left-[19px] top-8 bottom-8 w-px bg-border-dim sm:left-[27px]" aria-hidden="true" />
            <div className="space-y-4">
              {visibleRuns.map((run, index) => {
                const guide = STATUS_GUIDE[run.status];
                const planCount = run.summary?.candidate_plans.length ?? 0;
                return (
                  <article
                    key={run.run_id}
                    className="relative grid grid-cols-[40px_minmax(0,1fr)] gap-3 sm:grid-cols-[56px_minmax(0,1fr)] sm:gap-5"
                  >
                    <div className={`relative z-10 mt-6 flex h-10 w-10 items-center justify-center rounded-full border-4 border-void text-[9px] font-mono font-bold text-white sm:h-14 sm:w-14 ${guide.marker}`}>
                      {String(index + 1).padStart(2, '0')}
                    </div>
                    <div className="rounded-[1.5rem] border border-border-dim bg-abyss shadow-card overflow-hidden">
                      <div className={`h-1 ${guide.marker}`} />
                      <div className="p-5 sm:p-6">
                        <div className="flex flex-col sm:flex-row sm:items-start sm:justify-between gap-3">
                          <div>
                            <div className="flex flex-wrap items-center gap-2">
                              <span className="text-[9px] font-mono text-ink-muted">#{run.run_id}</span>
                              <span className={`rounded-full border px-2.5 py-1 text-[8px] font-mono font-semibold uppercase tracking-[0.1em] ${guide.badge}`}>
                                {guide.label}
                              </span>
                              {run.statusError && (
                                <span className="rounded-full border border-ops-orange/25 bg-ops-orange/10 px-2.5 py-1 text-[8px] font-mono text-ops-orange">
                                  saved status
                                </span>
                              )}
                            </div>
                            <p className="mt-2 text-[9px] font-mono text-ink-muted">{formatRunDate(run.created_at)}</p>
                          </div>
                          <div className="flex flex-wrap gap-2">
                            <button
                              type="button"
                              onClick={() => reuseGoal(run.goal_text)}
                              className="rounded-lg border border-border-base bg-deep px-3 py-2 text-[9px] font-semibold text-ink-secondary hover:text-ops-cyan focus-ring"
                            >
                              Use goal again
                            </button>
                            <Link
                              to={`/run/${run.run_id}`}
                              className="rounded-lg bg-ink-primary px-3 py-2 text-[9px] font-bold text-white hover:bg-ops-cyan focus-ring"
                            >
                              Open exact route &rarr;
                            </Link>
                          </div>
                        </div>

                        <h2 className="max-w-4xl text-base sm:text-lg font-extrabold leading-snug tracking-[-0.025em] text-ink-primary mt-5">
                          {run.goal_text}
                        </h2>

                        <div className="grid md:grid-cols-2 gap-3 mt-5">
                          <div className="rounded-xl border border-border-dim bg-deep/55 p-4">
                            <p className="text-[8px] font-mono font-semibold uppercase tracking-[0.14em] text-ink-muted">
                              What this status means
                            </p>
                            <p className="text-[11px] leading-relaxed text-ink-secondary mt-2">
                              {guide.explanation}
                            </p>
                          </div>
                          <div className="rounded-xl border border-ops-cyan/20 bg-ops-cyan/[0.04] p-4">
                            <p className="text-[8px] font-mono font-semibold uppercase tracking-[0.14em] text-ops-cyan">
                              Your next sensible move
                            </p>
                            <p className="text-[11px] leading-relaxed text-ink-secondary mt-2">
                              {guide.next}
                            </p>
                          </div>
                        </div>

                        {run.summary && (
                          <div className="flex flex-wrap gap-x-5 gap-y-2 mt-4 pt-4 border-t border-border-dim text-[9px] font-mono text-ink-muted">
                            <span>{planCount} candidate {planCount === 1 ? 'plan' : 'plans'}</span>
                            <span>{run.summary.replan_count} replans</span>
                            <span>{run.summary.excluded_specialist_incidents.length} blocked pairings</span>
                            <span>current card: {run.summary.current_node?.replace(/_/g, ' ') ?? 'not reported'}</span>
                          </div>
                        )}
                      </div>
                    </div>
                  </article>
                );
              })}
            </div>
          </div>
        )}
      </section>
    </div>
  );
}

export { DemoLabPage } from './DemoLabPage';

export function SettingsPage() {
  return (
    <WorkspacePage
      eyebrow="Settings"
      title="Make OptiFlow work your way."
      description="Control appearance, guided playback, motion, and how much engine detail is revealed while a decision unfolds."
      purpose="Personalize without hiding the truth"
      capabilities={[
        'Choose light, dark, or system appearance.',
        'Adjust readable step timing and reduced-motion behavior.',
        'Choose rules-only or AI-assisted explanations when available.',
      ]}
    />
  );
}
