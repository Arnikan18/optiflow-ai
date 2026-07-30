import { Link } from 'react-router-dom';
import { HealthStrip } from '../components/health/HealthStrip';
import { TodayDecisionBoard } from '../components/today/TodayDecisionBoard';
import type { RecentRun } from '../types/api';

const STATUS_STYLE: Record<string, string> = {
  COMPLETED: 'text-ops-emerald bg-ops-emerald/10',
  FAILED: 'text-ops-rose bg-ops-rose/10',
  RUNNING: 'text-ops-cyan bg-ops-cyan/10',
  WAITING_FOR_APPROVAL: 'text-ops-amber bg-ops-amber/10',
  WAITING_FOR_CLARIFICATION: 'text-ops-orange bg-ops-orange/10',
  EXECUTING: 'text-ops-orange bg-ops-orange/10',
  RECEIVED: 'text-ink-secondary bg-surface',
};

function readRecentRuns(): RecentRun[] {
  try {
    return JSON.parse(localStorage.getItem('optiflow_runs') ?? '[]') as RecentRun[];
  } catch {
    return [];
  }
}

function RecentWork() {
  const runs = readRecentRuns().slice(0, 3);
  if (runs.length === 0) return null;

  return (
    <section className="max-w-7xl mx-auto px-5 sm:px-8 py-10" aria-labelledby="recent-work-title">
      <div className="flex items-end justify-between gap-4 mb-5">
        <div>
          <p className="text-[9px] font-mono uppercase tracking-[0.18em] text-ink-muted">
            Continue today
          </p>
          <h2 id="recent-work-title" className="text-xl font-extrabold tracking-[-0.035em] mt-2">
            Your latest decision routes
          </h2>
        </div>
        <Link
          to="/history"
          className="text-[10px] font-semibold text-ink-secondary hover:text-ops-amber focus-ring rounded"
        >
          View all history →
        </Link>
      </div>
      <div className="grid md:grid-cols-3 gap-3">
        {runs.map((run) => (
          <Link
            key={run.run_id}
            to={`/run/${run.run_id}`}
            className="group rounded-2xl border border-border-dim bg-abyss p-5 hover:-translate-y-0.5 hover:shadow-card hover:border-border-base transition-all focus-ring"
          >
            <div className="flex items-center justify-between gap-3">
              <span className="text-[9px] font-mono text-ink-muted">
                #{run.run_id.slice(0, 8)}
              </span>
              <span className={`text-[8px] font-mono font-semibold px-2 py-1 rounded-full uppercase ${STATUS_STYLE[run.status] ?? 'text-ink-muted bg-surface'}`}>
                {run.status.replace(/_/g, ' ')}
              </span>
            </div>
            <p className="text-sm font-bold leading-relaxed text-ink-primary line-clamp-2 mt-4">
              {run.goal_text}
            </p>
            <p className="text-[10px] text-ink-muted mt-4">
              Open the route and review any completed card.
            </p>
            <span className="inline-block text-xs font-bold text-ops-amber mt-4 group-hover:translate-x-1 transition-transform">
              Continue →
            </span>
          </Link>
        ))}
      </div>
    </section>
  );
}

export function ControlRoomPage() {
  return (
    <div className="min-h-full paper-noise">
      <HealthStrip />
      <TodayDecisionBoard />
      <RecentWork />
    </div>
  );
}
