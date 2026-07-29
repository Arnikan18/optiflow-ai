import { useState } from 'react';
import { Link } from 'react-router-dom';
import { HealthStrip } from '../components/health/HealthStrip';
import { PortfolioPulse } from '../components/portfolio/PortfolioPulse';
import { GoalInput } from '../components/run/GoalInput';
import { api } from '../api/client';
import type { RecentRun } from '../types/api';

type IconName = 'target' | 'shield' | 'database' | 'balance' | 'hand' | 'check' | 'users' | 'message';

function Icon({ name, className = 'w-5 h-5' }: { name: IconName; className?: string }) {
  const paths: Record<IconName, React.ReactNode> = {
    target: <><circle cx="12" cy="12" r="8" /><circle cx="12" cy="12" r="3" /><path d="M12 2v3M22 12h-3" /></>,
    shield: <><path d="M12 3 5 6v5c0 4.7 2.9 8.1 7 10 4.1-1.9 7-5.3 7-10V6l-7-3Z" /><path d="m9 12 2 2 4-4" /></>,
    database: <><ellipse cx="12" cy="5" rx="7" ry="3" /><path d="M5 5v6c0 1.7 3.1 3 7 3s7-1.3 7-3V5M5 11v6c0 1.7 3.1 3 7 3s7-1.3 7-3v-6" /></>,
    balance: <><path d="M12 3v18M5 7h14M5 7l-3 6h6L5 7ZM19 7l-3 6h6l-3-6ZM8 21h8" /></>,
    hand: <><path d="M7 11V7a2 2 0 0 1 4 0v3-5a2 2 0 0 1 4 0v5-3a2 2 0 0 1 4 0v7c0 4-2.5 7-7 7h-1c-2.2 0-3.5-.8-5-2.5L2.7 14A2 2 0 0 1 6 11.8L7 13v-2Z" /></>,
    check: <><circle cx="12" cy="12" r="9" /><path d="m8 12 2.5 2.5L16 9" /></>,
    users: <><path d="M16 20v-1.5c0-2.5-2-4.5-4.5-4.5h-4A4.5 4.5 0 0 0 3 18.5V20M9.5 10A3.5 3.5 0 1 0 9.5 3a3.5 3.5 0 0 0 0 7ZM17 4a3 3 0 0 1 0 6M18 14c1.8.7 3 2.4 3 4.5V20" /></>,
    message: <><path d="M4 5h16v11H9l-5 4V5Z" /><path d="M8 9h8M8 12h5" /></>,
  };

  return (
    <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.7" strokeLinecap="round" strokeLinejoin="round" className={className} aria-hidden="true">
      {paths[name]}
    </svg>
  );
}

const JOURNEY = [
  { n: '01', name: 'Frame', detail: 'Turn the goal into clear priorities', icon: 'target' as IconName },
  { n: '02', name: 'Guard', detail: 'Check policy and missing rules', icon: 'shield' as IconName },
  { n: '03', name: 'Gather', detail: 'Collect live operational evidence', icon: 'database' as IconName },
  { n: '04', name: 'Compare', detail: 'Make trade-offs visible', icon: 'balance' as IconName },
  { n: '05', name: 'Decide', detail: 'Pause for your approval', icon: 'hand' as IconName },
  { n: '06', name: 'Verify', detail: 'Execute safely and confirm every write', icon: 'check' as IconName },
];

const ENGINES = [
  {
    code: '01 / CRM',
    title: 'Customer value',
    icon: 'users' as IconName,
    color: 'text-ops-violet',
    bg: 'bg-ops-violet/10',
    checks: ['Customer tier and ARR', 'Renewal proximity', 'Account status'],
    question: 'Who carries the greatest business impact?',
  },
  {
    code: '02 / INCIDENT',
    title: 'Service urgency',
    icon: 'shield' as IconName,
    color: 'text-ops-rose',
    bg: 'bg-ops-rose/10',
    checks: ['Priority and open status', 'Time until SLA breach', 'Existing ownership'],
    question: 'What needs attention first?',
  },
  {
    code: '03 / WORKFORCE',
    title: 'Team capacity',
    icon: 'users' as IconName,
    color: 'text-ops-cyan',
    bg: 'bg-ops-cyan/10',
    checks: ['Skills and availability', 'Current workload', 'Reservation conflicts'],
    question: 'Who can take this safely?',
  },
  {
    code: '04 / COMMS',
    title: 'Clear hand-off',
    icon: 'message' as IconName,
    color: 'text-ops-orange',
    bg: 'bg-ops-orange/10',
    checks: ['Recipient and channel', 'Delivery confirmation', 'Duplicate notifications'],
    question: 'Did everyone receive the decision?',
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

function RecentRuns() {
  const runs: RecentRun[] = (() => {
    try {
      return JSON.parse(localStorage.getItem('optiflow_runs') ?? '[]');
    } catch {
      return [];
    }
  })();

  if (runs.length === 0) return null;

  return (
    <section className="max-w-7xl mx-auto px-5 sm:px-8 pb-20">
      <div className="flex items-end justify-between mb-5">
        <div>
          <p className="text-[10px] font-mono uppercase tracking-[0.2em] text-ink-muted">Continue where you left off</p>
          <h2 className="text-2xl font-bold tracking-[-0.03em] mt-2">Recent decision routes</h2>
        </div>
      </div>
      <div className="grid md:grid-cols-2 lg:grid-cols-3 gap-3">
        {runs.slice(0, 6).map((run) => (
          <Link
            key={run.run_id}
            to={`/run/${run.run_id}`}
            className="group rounded-2xl border border-border-dim bg-abyss p-5 hover:-translate-y-0.5 hover:shadow-card hover:border-border-base transition-all focus-ring"
          >
            <div className="flex justify-between gap-3 mb-4">
              <span className="text-[10px] font-mono text-ink-muted">#{run.run_id.slice(0, 8)}</span>
              <span className={`text-[9px] font-mono font-semibold px-2 py-1 rounded-full uppercase ${STATUS_STYLE[run.status] ?? 'text-ink-muted bg-surface'}`}>
                {run.status.replace(/_/g, ' ')}
              </span>
            </div>
            <p className="text-sm font-semibold leading-relaxed text-ink-primary line-clamp-2">{run.goal_text}</p>
            <div className="mt-5 text-xs font-semibold text-ops-amber group-hover:translate-x-1 transition-transform">
              Open route →
            </div>
          </Link>
        ))}
      </div>
    </section>
  );
}

export function ControlRoomPage() {
  const [resetting, setResetting] = useState(false);
  const [resetMsg, setResetMsg] = useState<string | null>(null);

  const handleReset = async () => {
    setResetting(true);
    setResetMsg(null);
    try {
      await api.resetDemo();
      setResetMsg('Demo data refreshed and ready.');
    } catch (err: unknown) {
      setResetMsg(err instanceof Error ? err.message : 'Reset failed');
    } finally {
      setResetting(false);
    }
  };

  return (
    <div className="min-h-full paper-noise">
      <HealthStrip />
      <PortfolioPulse />

      <section className="relative overflow-hidden border-b border-border-dim">
        <div className="absolute top-0 right-0 w-[42%] h-full border-l border-border-dim bg-deep/55 hidden lg:block" />
        <div className="relative max-w-7xl mx-auto px-5 sm:px-8 pt-14 lg:pt-20 pb-16 lg:pb-24">
          <div className="grid lg:grid-cols-[0.88fr_1.12fr] gap-12 lg:gap-20 items-center">
            <div>
              <div className="inline-flex items-center gap-2 rounded-full border border-border-base bg-abyss px-3 py-1.5 mb-7">
                <span className="w-1.5 h-1.5 rounded-full bg-ops-amber" />
                <span className="text-[10px] font-mono font-semibold tracking-[0.16em] uppercase text-ink-secondary">
                  Guided portfolio decisions
                </span>
              </div>
              <h1 className="text-[clamp(2.65rem,6vw,5.2rem)] font-extrabold leading-[0.98] tracking-[-0.065em] text-ink-primary">
                A decision
                <span className="block text-ops-amber">you can explain.</span>
              </h1>
              <p className="text-base sm:text-lg leading-relaxed text-ink-secondary mt-7 max-w-xl">
                OptiFlow turns every escalation decision into a visible route—from your goal, through every check, to a human-approved outcome.
              </p>
              <div className="flex flex-wrap gap-x-7 gap-y-3 mt-8">
                {['No hidden steps', 'Approval before action', 'Full audit trail'].map((item) => (
                  <span key={item} className="flex items-center gap-2 text-xs font-semibold text-ink-secondary">
                    <span className="w-5 h-5 rounded-full bg-ops-emerald/10 text-ops-emerald flex items-center justify-center">✓</span>
                    {item}
                  </span>
                ))}
              </div>
            </div>

            <div className="relative min-w-0">
              <div className="absolute -inset-5 border border-border-dim rounded-[2rem] rotate-2" />
              <div className="relative rounded-[1.75rem] bg-abyss border border-border-base shadow-card p-5 sm:p-7">
                <div className="flex items-start justify-between gap-4 mb-5">
                  <div>
                    <p className="text-[10px] font-mono text-ops-amber uppercase tracking-[0.18em] font-semibold">Start here</p>
                    <h2 className="text-xl font-bold tracking-[-0.03em] mt-1">What outcome do you need?</h2>
                  </div>
                  <div className="w-9 h-9 rounded-full border border-border-dim flex items-center justify-center text-xs font-mono text-ink-muted">01</div>
                </div>
                <GoalInput />
              </div>
            </div>
          </div>
        </div>
      </section>

      <section className="max-w-7xl mx-auto px-5 sm:px-8 py-20 lg:py-28">
        <div className="grid lg:grid-cols-[0.72fr_1.28fr] gap-12 lg:gap-24">
          <div>
            <p className="text-[10px] font-mono uppercase tracking-[0.2em] text-ops-cyan font-semibold">The decision route</p>
            <h2 className="text-3xl sm:text-5xl leading-tight font-extrabold tracking-[-0.055em] mt-4">
              You always know where you are.
            </h2>
            <p className="text-sm sm:text-base leading-relaxed text-ink-secondary mt-5 max-w-md">
              The route stays visible while OptiFlow works. Each station explains what is being checked, why it matters, and when you need to act.
            </p>
            <div className="mt-8 rounded-2xl bg-ink-primary text-white p-5 max-w-sm">
              <p className="text-[10px] font-mono uppercase tracking-[0.18em] text-white/50">Promise</p>
              <p className="text-sm leading-relaxed mt-2 text-white/90">
                If the AI stops, the route still teaches a manager how to make the decision manually.
              </p>
            </div>
          </div>

          <div className="route-track space-y-3">
            {JOURNEY.map((step, index) => (
              <div key={step.n} className="relative pl-14 group">
                <div className={`absolute left-0 top-3 z-10 w-9 h-9 rounded-full border flex items-center justify-center font-mono text-[10px] font-semibold transition-all ${
                  index === 0
                    ? 'bg-ops-amber text-white border-ops-amber route-pulse'
                    : 'bg-abyss text-ink-muted border-border-base group-hover:border-ops-cyan group-hover:text-ops-cyan'
                }`}>
                  {step.n}
                </div>
                <div className="rounded-2xl border border-border-dim bg-abyss px-5 py-4 flex items-center gap-4 group-hover:border-border-base group-hover:shadow-card transition-all">
                  <div className="w-10 h-10 rounded-xl bg-deep flex items-center justify-center text-ops-cyan">
                    <Icon name={step.icon} />
                  </div>
                  <div className="flex-1">
                    <div className="font-bold text-sm">{step.name}</div>
                    <div className="text-xs text-ink-muted mt-1">{step.detail}</div>
                  </div>
                  <span className="text-ink-ghost group-hover:text-ops-amber transition-colors">→</span>
                </div>
              </div>
            ))}
          </div>
        </div>
      </section>

      <section className="border-y border-border-dim bg-abyss">
        <div className="max-w-7xl mx-auto px-5 sm:px-8 py-20 lg:py-24">
          <div className="max-w-2xl mb-12">
            <p className="text-[10px] font-mono uppercase tracking-[0.2em] text-ops-violet font-semibold">Inside the evidence stage</p>
            <h2 className="text-3xl sm:text-4xl font-extrabold tracking-[-0.05em] mt-3">Four engines. Four clear questions.</h2>
            <p className="text-sm text-ink-secondary mt-4 leading-relaxed">
              OptiFlow shows the check—not just the result—so a human can challenge it, verify it, or reproduce it.
            </p>
          </div>
          <div className="grid sm:grid-cols-2 lg:grid-cols-4 border-l border-t border-border-dim">
            {ENGINES.map((engine) => (
              <article key={engine.code} className="min-h-[330px] border-r border-b border-border-dim p-6 flex flex-col hover:bg-deep transition-colors">
                <div className={`w-11 h-11 rounded-2xl ${engine.bg} ${engine.color} flex items-center justify-center`}>
                  <Icon name={engine.icon} />
                </div>
                <p className="text-[9px] font-mono tracking-[0.16em] text-ink-muted mt-6">{engine.code}</p>
                <h3 className="text-lg font-bold tracking-[-0.03em] mt-2">{engine.title}</h3>
                <ul className="space-y-2.5 mt-5">
                  {engine.checks.map((check) => (
                    <li key={check} className="flex gap-2 text-xs text-ink-secondary">
                      <span className={`${engine.color}`}>—</span>
                      {check}
                    </li>
                  ))}
                </ul>
                <p className={`mt-auto pt-7 text-xs font-semibold leading-relaxed ${engine.color}`}>{engine.question}</p>
              </article>
            ))}
          </div>
        </div>
      </section>

      <section className="max-w-7xl mx-auto px-5 sm:px-8 py-20">
        <div className="rounded-[2rem] bg-ink-primary text-white overflow-hidden grid lg:grid-cols-[1.15fr_0.85fr]">
          <div className="p-7 sm:p-10 lg:p-14">
            <p className="text-[10px] font-mono uppercase tracking-[0.2em] text-[#ff8a64]">Manual fallback card</p>
            <h2 className="text-3xl sm:text-4xl font-extrabold tracking-[-0.045em] mt-4 max-w-xl">
              No AI? Make the same decision in four checks.
            </h2>
            <p className="text-sm leading-relaxed text-white/60 mt-5 max-w-xl">
              Use this sequence to keep the decision defensible when automation is unavailable.
            </p>
          </div>
          <ol className="border-t lg:border-t-0 lg:border-l border-white/10">
            {[
              'Rank open incidents by SLA deadline.',
              'Overlay customer tier, ARR, and renewal risk.',
              'Match required skills to available capacity.',
              'Record the trade-off and get human approval.',
            ].map((item, index) => (
              <li key={item} className="flex gap-4 p-5 sm:px-7 border-b last:border-b-0 border-white/10">
                <span className="text-[10px] font-mono text-[#ff8a64] pt-0.5">0{index + 1}</span>
                <span className="text-sm text-white/80">{item}</span>
              </li>
            ))}
          </ol>
        </div>
      </section>

      <RecentRuns />

      <footer className="border-t border-border-dim bg-abyss">
        <div className="max-w-7xl mx-auto px-5 sm:px-8 py-6 flex flex-col sm:flex-row items-start sm:items-center justify-between gap-3">
          <p className="text-[10px] font-mono uppercase tracking-[0.16em] text-ink-muted">OptiFlow decision canvas · phase 2</p>
          <div className="flex items-center gap-3">
            {resetMsg && <span className="text-xs text-ink-secondary">{resetMsg}</span>}
            <button
              onClick={handleReset}
              disabled={resetting}
              className="text-xs font-semibold text-ink-secondary hover:text-ops-amber disabled:opacity-40 transition-colors focus-ring rounded"
            >
              {resetting ? 'Refreshing…' : 'Refresh demo data'}
            </button>
          </div>
        </div>
      </footer>
    </div>
  );
}
