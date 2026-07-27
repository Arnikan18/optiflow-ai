import { useState } from 'react';
import { Link } from 'react-router-dom';
import { HealthStrip } from '../components/health/HealthStrip';
import { GoalInput } from '../components/run/GoalInput';
import { api } from '../api/client';
import type { RecentRun } from '../types/api';

const STATUS_STYLE: Record<string, string> = {
  COMPLETED:                 'text-ops-emerald bg-ops-emerald/10',
  FAILED:                    'text-ops-rose bg-ops-rose/10',
  RUNNING:                   'text-ops-cyan bg-ops-cyan/10',
  WAITING_FOR_APPROVAL:      'text-ops-amber bg-ops-amber/10',
  WAITING_FOR_CLARIFICATION: 'text-ops-orange bg-ops-orange/10',
  EXECUTING:                 'text-ops-orange bg-ops-orange/10',
  RECEIVED:                  'text-ink-secondary bg-border-dim',
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
    <div className="space-y-3">
      <p className="text-xs font-mono text-ink-muted uppercase tracking-widest">Recent Runs</p>
      <div className="space-y-2">
        {runs.slice(0, 6).map((r) => (
          <Link
            key={r.run_id}
            to={`/run/${r.run_id}`}
            className="flex items-center gap-3 p-3 bg-deep border border-border-dim rounded-lg
              hover:border-border-base hover:bg-surface transition-all duration-200 group"
          >
            <div className="flex-1 min-w-0">
              <p className="text-xs font-mono text-ink-secondary group-hover:text-ink-primary truncate transition-colors">
                {r.run_id}
              </p>
              <p className="text-xs text-ink-muted truncate mt-0.5">{r.goal_text}</p>
            </div>
            <span className={`text-xs font-mono px-2 py-0.5 rounded shrink-0 uppercase ${STATUS_STYLE[r.status] ?? 'text-ink-muted'}`}>
              {r.status}
            </span>
          </Link>
        ))}
      </div>
    </div>
  );
}

function HowItWorks() {
  const steps = [
    { n: '01', title: 'Submit a Goal', desc: 'Type your operational objective in plain English. The AI interprets it, validates it against policies, and gathers live data from all four enterprise services.' },
    { n: '02', title: 'Watch the Agent Work', desc: 'Every action the agent takes is streamed to you in real time. You can see exactly which tools were queried, what evidence was found, and how plans were scored.' },
    { n: '03', title: 'Review 4 Candidate Plans', desc: 'The CP-SAT solver generates Balanced, SLA-First, Revenue-First, and Fairness-First allocations. Compare metrics side-by-side and read AI-generated Markdown explanations.' },
    { n: '04', title: 'Approve and Execute', desc: 'Only after your explicit approval do any changes commit to enterprise systems. A SAGA transaction pattern ensures safe, rollback-capable execution.' },
  ];

  return (
    <div className="space-y-4">
      <p className="text-xs font-mono text-ink-muted uppercase tracking-widest">How It Works</p>
      <div className="space-y-3">
        {steps.map((s) => (
          <div key={s.n} className="flex gap-4 p-4 bg-deep border border-border-dim rounded-lg">
            <span className="text-2xl font-bold font-mono text-border-base shrink-0 leading-none">{s.n}</span>
            <div>
              <p className="text-sm font-semibold text-ink-primary mb-1">{s.title}</p>
              <p className="text-xs text-ink-muted leading-relaxed">{s.desc}</p>
            </div>
          </div>
        ))}
      </div>
    </div>
  );
}

export function ControlRoomPage() {
  const [resetting, setResetting] = useState(false);
  const [resetMsg, setResetMsg] = useState<string | null>(null);

  const handleReset = async () => {
    setResetting(true);
    setResetMsg(null);
    try {
      await api.resetSystem();
      setResetMsg('System reset successfully. Demo data has been seeded.');
    } catch (err: unknown) {
      const msg = err instanceof Error ? err.message : 'Reset failed';
      setResetMsg(`Error: ${msg}`);
    } finally {
      setResetting(false);
    }
  };

  return (
    <div className="min-h-screen bg-void bg-grid bg-grid-ops">
      <HealthStrip />

      {/* Page header */}
      <div className="px-6 pt-10 pb-6 border-b border-border-dim">
        <div className="max-w-6xl mx-auto flex items-start justify-between gap-6">
          <div className="space-y-2">
            <div className="flex items-center gap-2 text-xs font-mono text-ink-muted uppercase tracking-widest">
              <span>OptiFlow AI</span>
              <span className="text-border-base">›</span>
              <span className="text-ink-secondary">Control Room</span>
            </div>
            <h1 className="text-2xl font-bold text-ink-primary">
              Portfolio Decision <span className="text-ops-amber">Control Room</span>
            </h1>
            <p className="text-sm text-ink-secondary max-w-xl leading-relaxed">
              Human-governed autonomous allocation for B2B SaaS customer escalations. The AI proposes — you decide.
            </p>
          </div>

          {/* Demo reset button */}
          <div className="shrink-0 space-y-2">
            <button
              onClick={handleReset}
              disabled={resetting}
              className="flex items-center gap-2 px-4 py-2 bg-surface border border-border-base rounded-lg
                text-xs font-mono text-ink-secondary hover:border-ops-amber hover:text-ink-primary
                disabled:opacity-40 transition-all duration-200"
            >
              {resetting ? (
                <span className="w-3 h-3 border border-current/30 border-t-current rounded-full animate-spin" />
              ) : (
                <span>↺</span>
              )}
              Reset Demo Data
            </button>
            {resetMsg && (
              <p className={`text-xs font-mono ${resetMsg.startsWith('Error') ? 'text-ops-rose' : 'text-ops-emerald'}`}>
                {resetMsg}
              </p>
            )}
          </div>
        </div>
      </div>

      {/* Main content */}
      <div className="max-w-6xl mx-auto px-6 py-8">
        <div className="grid grid-cols-1 lg:grid-cols-5 gap-8">
          {/* Left: Goal submission */}
          <div className="lg:col-span-3 space-y-8">
            <div className="bg-abyss border border-border-dim rounded-2xl p-6">
              <h2 className="text-sm font-semibold text-ink-primary mb-1">New Decision Run</h2>
              <p className="text-xs text-ink-muted mb-5 leading-relaxed">
                Describe your operational objective. The agent will interpret your goal, gather evidence from all enterprise services, generate optimised allocation plans, and wait for your approval before executing any changes.
              </p>
              <GoalInput />
            </div>

            <HowItWorks />
          </div>

          {/* Right: Recent runs + key concepts */}
          <div className="lg:col-span-2 space-y-6">
            <RecentRuns />

            {/* Key concepts callout */}
            <div className="bg-abyss border border-border-dim rounded-2xl p-5 space-y-4">
              <p className="text-xs font-mono text-ops-amber uppercase tracking-widest">
                When AI Is Unavailable
              </p>
              <p className="text-xs text-ink-secondary leading-relaxed">
                This system is designed to teach you the decision logic, not replace it. Even without the AI, a defensible allocation decision requires: knowing each customer's ARR and tier, understanding SLA deadlines across all open incidents, checking specialist availability and workload, and explicitly choosing which trade-off you're accepting.
              </p>
              <div className="space-y-2">
                {[
                  ['CRM', 'Who are my highest-ARR customers?', '8101'],
                  ['Incident', 'Which incidents breach SLA first?', '8102'],
                  ['Workforce', 'Who is available and underloaded?', '8103'],
                ].map(([svc, q, port]) => (
                  <div key={svc} className="flex items-start gap-2">
                    <span className="text-xs font-mono text-border-bright shrink-0 mt-0.5">{svc}</span>
                    <div>
                      <p className="text-xs text-ink-muted">{q}</p>
                      <p className="text-xs text-ink-ghost font-mono">port {port}</p>
                    </div>
                  </div>
                ))}
              </div>
            </div>
          </div>
        </div>
      </div>
    </div>
  );
}
