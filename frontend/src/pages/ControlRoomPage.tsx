import { Link } from 'react-router-dom';
import { HealthStrip } from '../components/health/HealthStrip';
import { PortfolioPulse } from '../components/portfolio/PortfolioPulse';
import { GoalInput } from '../components/run/GoalInput';
import type { RecentRun } from '../types/api';

const ROUTE_STAGES = [
  {
    number: '01',
    label: 'Frame',
    detail: 'Translate your words into priorities, limits, and a timeframe.',
  },
  {
    number: '02',
    label: 'Guard',
    detail: 'Check policy, missing information, and whether a human must decide.',
  },
  {
    number: '03',
    label: 'Gather',
    detail: 'Read customer, incident, and workforce evidence from each engine.',
  },
  {
    number: '04',
    label: 'Compare',
    detail: 'Build four plans and make the operational tradeoffs visible.',
  },
  {
    number: '05',
    label: 'Approve',
    detail: 'Stop for your approval, change request, or manual decision.',
  },
  {
    number: '06',
    label: 'Verify',
    detail: 'Apply the approved route safely and confirm every result.',
  },
];

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
  const today = new Intl.DateTimeFormat('en-US', {
    weekday: 'long',
    month: 'long',
    day: 'numeric',
  }).format(new Date());

  return (
    <div className="min-h-full paper-noise">
      <HealthStrip />

      <section className="border-b border-border-dim">
        <div className="max-w-7xl mx-auto px-5 sm:px-8 py-10 lg:py-14">
          <div className="flex flex-col lg:flex-row lg:items-end justify-between gap-6">
            <div>
              <div className="flex items-center gap-3">
                <span className="text-[9px] font-mono font-semibold uppercase tracking-[0.2em] text-ops-amber">
                  Today’s goal
                </span>
                <span className="h-px w-8 bg-border-base" />
                <span className="text-[9px] font-mono text-ink-muted">{today}</span>
              </div>
              <h1 className="max-w-4xl text-[clamp(2.6rem,6vw,5.6rem)] font-extrabold leading-[0.94] tracking-[-0.07em] mt-5">
                Name the outcome.
                <span className="block text-ops-amber">Watch every decision move.</span>
              </h1>
            </div>
            <div className="max-w-sm lg:pb-2">
              <p className="text-sm leading-relaxed text-ink-secondary">
                OptiFlow turns one operational goal into a visible, human-governed route. Each card will show
                what was checked, why it mattered, and what you can do manually.
              </p>
              <div className="grid grid-cols-3 gap-3 mt-5">
                {[
                  ['Visible', 'reasoning'],
                  ['Human', 'approval'],
                  ['Verified', 'outcome'],
                ].map(([value, label]) => (
                  <div key={value} className="border-l border-border-base pl-3">
                    <p className="text-[10px] font-bold text-ink-primary">{value}</p>
                    <p className="text-[9px] text-ink-muted mt-0.5">{label}</p>
                  </div>
                ))}
              </div>
            </div>
          </div>

          <div className="grid lg:grid-cols-[minmax(0,1.35fr)_minmax(280px,0.65fr)] gap-4 mt-10">
            <article className="rounded-[1.75rem] border border-border-base bg-abyss shadow-card overflow-hidden">
              <div className="h-1.5 bg-ops-amber" />
              <div className="p-5 sm:p-7">
                <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-3 mb-5">
                  <div>
                    <p className="text-[9px] font-mono uppercase tracking-[0.18em] text-ops-amber">
                      Decision brief
                    </p>
                    <h2 className="text-xl sm:text-2xl font-extrabold tracking-[-0.04em] mt-1">
                      What must be true by the end of today?
                    </h2>
                  </div>
                  <span className="self-start sm:self-auto rounded-full border border-ops-emerald/30 bg-ops-emerald/5 px-3 py-1.5 text-[9px] font-mono uppercase tracking-[0.12em] text-ops-emerald">
                    No action before approval
                  </span>
                </div>
                <GoalInput />
              </div>
            </article>

            <aside className="rounded-[1.75rem] border border-border-dim bg-ink-primary text-white overflow-hidden">
              <div className="p-5 sm:p-6">
                <p className="text-[9px] font-mono uppercase tracking-[0.18em] text-[#ff8a64]">
                  What moves next
                </p>
                <p className="text-sm leading-relaxed text-white/60 mt-3">
                  Cards arrive in this order and stay open for review.
                </p>
                <ol className="mt-5">
                  {ROUTE_STAGES.map((stage) => (
                    <li key={stage.number} className="grid grid-cols-[28px_1fr] gap-3 py-3 border-t border-white/10 first:border-t-0">
                      <span className="text-[9px] font-mono text-[#ff8a64] pt-0.5">
                        {stage.number}
                      </span>
                      <div>
                        <p className="text-xs font-bold text-white">{stage.label}</p>
                        <p className="text-[10px] leading-relaxed text-white/55 mt-1">{stage.detail}</p>
                      </div>
                    </li>
                  ))}
                </ol>
              </div>
            </aside>
          </div>
        </div>
      </section>

      <PortfolioPulse />

      <section className="border-b border-border-dim bg-abyss">
        <div className="max-w-7xl mx-auto px-5 sm:px-8 py-10">
          <div className="flex flex-col lg:flex-row lg:items-center justify-between gap-5">
            <div className="max-w-xl">
              <p className="text-[9px] font-mono uppercase tracking-[0.18em] text-ops-cyan">
                Manual route remains available
              </p>
              <h2 className="text-2xl font-extrabold tracking-[-0.04em] mt-2">
                Automation may assist. The method never disappears.
              </h2>
            </div>
            <ol className="grid sm:grid-cols-3 gap-3 lg:max-w-2xl">
              {[
                'Rank urgency and business impact.',
                'Match skills without exceeding capacity.',
                'Record the tradeoff and approve the action.',
              ].map((instruction, index) => (
                <li key={instruction} className="rounded-xl border border-border-dim bg-deep p-4">
                  <span className="text-[8px] font-mono text-ops-cyan">0{index + 1}</span>
                  <p className="text-[11px] leading-relaxed text-ink-secondary mt-2">{instruction}</p>
                </li>
              ))}
            </ol>
          </div>
        </div>
      </section>

      <RecentWork />
    </div>
  );
}
