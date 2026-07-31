import { useEffect, useMemo, useState } from 'react';
import { Link, useNavigate } from 'react-router-dom';
import { api } from '../api/client';
import type { RecentRun, RunStatus, RunSummary } from '../types/api';

type DecisionRecord = RecentRun & {
  summary: RunSummary | null;
  unavailable: boolean;
};

type View = 'all' | 'attention' | 'closed';

const ATTENTION = new Set<RunStatus>([
  'WAITING_FOR_APPROVAL',
  'WAITING_FOR_CLARIFICATION',
  'FAILED_SAGA',
  'FAILED',
]);
const CLOSED = new Set<RunStatus>(['COMPLETED', 'CANCELLED', 'FAILED']);

const STATUS: Record<RunStatus, { label: string; tone: string }> = {
  RECEIVED: { label: 'Received', tone: 'border-border-base text-ink-secondary' },
  RUNNING: { label: 'Working', tone: 'border-ops-cyan/35 text-ops-cyan' },
  WAITING_FOR_CLARIFICATION: { label: 'Answer needed', tone: 'border-ops-orange/35 text-ops-orange' },
  WAITING_FOR_APPROVAL: { label: 'Decision needed', tone: 'border-ops-amber/35 text-ops-amber' },
  EXECUTING: { label: 'Executing', tone: 'border-ops-orange/35 text-ops-orange' },
  REPLANNING: { label: 'Replanning', tone: 'border-ops-violet/35 text-ops-violet' },
  EXECUTED: { label: 'Executed', tone: 'border-ops-cyan/35 text-ops-cyan' },
  FAILED_SAGA: { label: 'Review execution', tone: 'border-ops-rose/35 text-ops-rose' },
  COMPLETED: { label: 'Complete', tone: 'border-ops-emerald/35 text-ops-emerald' },
  FAILED: { label: 'Stopped safely', tone: 'border-ops-rose/35 text-ops-rose' },
  CANCELLED: { label: 'Cancelled', tone: 'border-border-base text-ink-secondary' },
};

function readRecords(): DecisionRecord[] {
  try {
    const saved = JSON.parse(localStorage.getItem('optiflow_runs') ?? '[]') as RecentRun[];
    return saved.map((record) => ({ ...record, summary: null, unavailable: false }));
  } catch {
    return [];
  }
}

function dateLabel(value: string): string {
  const date = new Date(value);
  if (Number.isNaN(date.getTime())) return 'Time not recorded';
  return new Intl.DateTimeFormat('en-US', {
    month: 'short',
    day: 'numeric',
    hour: '2-digit',
    minute: '2-digit',
  }).format(date);
}

export function DecisionsPage() {
  const navigate = useNavigate();
  const [records, setRecords] = useState<DecisionRecord[]>(readRecords);
  const [view, setView] = useState<View>('all');
  const [refreshing, setRefreshing] = useState(records.length > 0);

  useEffect(() => {
    let cancelled = false;
    const refresh = async () => {
      const next = await Promise.all(records.map(async (record): Promise<DecisionRecord> => {
        try {
          const summary = await api.getRunStatus(record.run_id);
          return { ...record, status: summary.status, summary, unavailable: false };
        } catch {
          return { ...record, summary: null, unavailable: true };
        }
      }));
      if (!cancelled) {
        setRecords(next);
        setRefreshing(false);
      }
    };
    if (records.length) void refresh();
    else setRefreshing(false);
    return () => {
      cancelled = true;
    };
    // Refresh the browser snapshot once when this page opens.
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  const visible = useMemo(() => records.filter((record) => {
    if (view === 'attention') return ATTENTION.has(record.status);
    if (view === 'closed') return CLOSED.has(record.status);
    return true;
  }), [records, view]);

  const counts = {
    all: records.length,
    attention: records.filter((record) => ATTENTION.has(record.status)).length,
    closed: records.filter((record) => CLOSED.has(record.status)).length,
  };

  const reuseGoal = (goal: string) => {
    sessionStorage.setItem('optiflow_goal_draft', goal);
    navigate('/');
  };

  return (
    <div className="min-h-full paper-noise">
      <header className="border-b border-border-dim bg-abyss">
        <div className="mx-auto max-w-6xl px-5 py-9 sm:px-8">
          <div className="flex flex-wrap items-end justify-between gap-4">
            <div>
              <p className="text-sm font-bold text-ops-cyan">Decision history</p>
              <h1 className="mt-1 text-3xl font-extrabold tracking-[-0.045em] text-ink-primary sm:text-4xl">
                Continue or review a route
              </h1>
            </div>
            <span className="text-sm text-ink-muted">
              {refreshing ? 'Refreshing from Core…' : `${records.length} saved in this browser`}
            </span>
          </div>
        </div>
      </header>

      <main className="mx-auto max-w-6xl px-5 py-7 sm:px-8">
        <div className="flex flex-wrap gap-2" role="tablist" aria-label="Decision history filters">
          {([
            ['all', 'All'],
            ['attention', 'Needs me'],
            ['closed', 'Closed'],
          ] as const).map(([id, label]) => (
            <button
              key={id}
              type="button"
              role="tab"
              aria-selected={view === id}
              onClick={() => setView(id)}
              className={`min-h-11 rounded-xl border px-4 py-2 text-sm font-bold focus-ring ${
                view === id
                  ? 'border-ops-cyan bg-ops-cyan/[0.07] text-ops-cyan'
                  : 'border-border-dim bg-abyss text-ink-secondary'
              }`}
            >
              {label} · {counts[id]}
            </button>
          ))}
        </div>

        <div className="mt-5 space-y-3">
          {visible.map((record) => {
            const status = STATUS[record.status];
            return (
              <article key={record.run_id} className="rounded-2xl border border-border-dim bg-abyss p-5 shadow-card">
                <div className="flex flex-col justify-between gap-4 sm:flex-row sm:items-start">
                  <div className="min-w-0">
                    <div className="flex flex-wrap items-center gap-2">
                      <span className={`rounded-full border px-3 py-1 text-xs font-bold ${status.tone}`}>
                        {status.label}
                      </span>
                      <span className="text-sm text-ink-muted">{dateLabel(record.created_at)}</span>
                      {record.unavailable && <span className="text-xs text-ops-orange">Saved status</span>}
                    </div>
                    <h2 className="mt-3 text-lg font-extrabold leading-snug text-ink-primary">
                      {record.goal_text}
                    </h2>
                  </div>
                  <div className="flex shrink-0 flex-wrap gap-2">
                    <button
                      type="button"
                      onClick={() => reuseGoal(record.goal_text)}
                      className="min-h-11 rounded-xl border border-border-base bg-deep px-4 py-2 text-sm font-bold text-ink-secondary focus-ring"
                    >
                      Use goal again
                    </button>
                    <Link
                      to={`/run/${encodeURIComponent(record.run_id)}`}
                      className="inline-flex min-h-11 items-center rounded-xl bg-ink-primary px-4 py-2 text-sm font-bold text-white hover:bg-ops-cyan focus-ring"
                    >
                      Open route
                    </Link>
                  </div>
                </div>

                {record.summary && (
                  <details className="group mt-4 border-t border-border-dim pt-3">
                    <summary className="flex min-h-11 cursor-pointer list-none items-center justify-between rounded-xl text-sm font-bold text-ink-muted focus-ring">
                      <span>Route details</span>
                      <span className="text-xl text-ops-cyan transition-transform group-open:rotate-45">+</span>
                    </summary>
                    <div className="flex flex-wrap gap-4 pb-1 text-sm text-ink-secondary">
                      <span>{record.summary.candidate_plans.length} plans</span>
                      <span>{record.summary.replan_count} replans</span>
                      <span>Run {record.run_id}</span>
                    </div>
                  </details>
                )}
              </article>
            );
          })}

          {visible.length === 0 && (
            <div className="rounded-2xl border border-dashed border-border-base bg-abyss px-6 py-14 text-center">
              <p className="text-lg font-extrabold text-ink-primary">
                {records.length ? 'Nothing in this view.' : 'No decisions yet.'}
              </p>
              <Link to="/" className="mt-4 inline-flex min-h-11 items-center rounded-xl bg-ink-primary px-5 text-sm font-bold text-white focus-ring">
                Open Today
              </Link>
            </div>
          )}
        </div>
      </main>
    </div>
  );
}
