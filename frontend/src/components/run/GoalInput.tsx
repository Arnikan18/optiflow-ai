import { useEffect, useState } from 'react';
import { useNavigate } from 'react-router-dom';
import { api } from '../../api/client';
import type { RecentRun } from '../../types/api';

const GOAL_STARTERS = [
  {
    label: 'Revenue & renewal',
    signal: 'CRM + SLA',
    text: 'Protect high-ARR customers with renewal risk from SLA breach today, while keeping specialist workload below safe capacity.',
  },
  {
    label: 'Urgent coverage',
    signal: 'INCIDENT + WORKFORCE',
    text: 'Assign available qualified specialists to incidents closest to SLA breach today, without moving existing confirmed work.',
  },
  {
    label: 'Fair workload',
    signal: 'WORKFORCE + SLA',
    text: 'Rebalance today’s incident workload to reduce overload, preserve critical SLA coverage, and avoid unnecessary context switching.',
  },
];

function saveRecentRun(run_id: string, goal_text: string) {
  try {
    const existing: RecentRun[] = JSON.parse(localStorage.getItem('optiflow_runs') ?? '[]');
    const entry: RecentRun = {
      run_id,
      goal_text,
      status: 'RECEIVED',
      created_at: new Date().toISOString(),
    };
    localStorage.setItem('optiflow_runs', JSON.stringify([entry, ...existing].slice(0, 10)));
  } catch {
    // Local storage is optional.
  }
}

function readGoalDraft(): string {
  try {
    return sessionStorage.getItem('optiflow_goal_draft') ?? '';
  } catch {
    return '';
  }
}

export function GoalInput() {
  const [goal, setGoal] = useState(readGoalDraft);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const navigate = useNavigate();
  const isReady = goal.trim().length >= 10 && !loading;

  useEffect(() => {
    try {
      sessionStorage.removeItem('optiflow_goal_draft');
    } catch {
      // The prefilled draft remains in component state.
    }
  }, []);

  const handleSubmit = async (event: React.FormEvent) => {
    event.preventDefault();
    const trimmed = goal.trim();
    if (trimmed.length < 10) return;

    setLoading(true);
    setError(null);

    try {
      const { run_id } = await api.createRun(trimmed);
      saveRecentRun(run_id, trimmed);
      navigate(`/run/${run_id}`);
    } catch (err: unknown) {
      setError(err instanceof Error ? err.message : 'Failed to start the decision route');
      setLoading(false);
    }
  };

  return (
    <form onSubmit={handleSubmit} className="min-w-0">
      <div className="grid grid-cols-3 gap-2 mb-3" aria-label="A useful goal includes">
        {[
          ['01', 'Priority', 'What matters most'],
          ['02', 'Boundary', 'What must stay safe'],
          ['03', 'Timeframe', 'When it must happen'],
        ].map(([number, label, detail]) => (
          <div key={label} className="rounded-xl border border-border-dim bg-deep/70 px-3 py-2.5">
            <div className="flex items-center gap-2">
              <span className="text-[8px] font-mono text-ops-amber">{number}</span>
              <span className="text-[9px] font-bold text-ink-primary">{label}</span>
            </div>
            <p className="hidden sm:block text-[9px] text-ink-muted mt-1">{detail}</p>
          </div>
        ))}
      </div>

      <div className="rounded-2xl border border-border-base bg-deep overflow-hidden focus-within:border-ops-amber focus-within:ring-4 focus-within:ring-ops-amber/10 transition-all">
        <label
          htmlFor="decision-goal"
          className="block px-4 sm:px-5 pt-4 text-[9px] font-mono font-semibold uppercase tracking-[0.16em] text-ink-muted"
        >
          Outcome statement
        </label>
        <textarea
          id="decision-goal"
          value={goal}
          onChange={(event) => setGoal(event.target.value)}
          placeholder="Protect the customers closest to SLA breach today, without overloading the team."
          rows={5}
          maxLength={500}
          disabled={loading}
          aria-describedby="goal-guidance"
          className="w-full bg-transparent px-4 sm:px-5 py-3 text-ink-primary placeholder:text-ink-muted resize-none focus:outline-none text-sm sm:text-base leading-relaxed disabled:opacity-50"
        />
        <div className="px-4 sm:px-5 py-3 border-t border-border-dim flex items-center justify-between gap-3">
          <span id="goal-guidance" className="text-[10px] leading-relaxed text-ink-muted">
            {goal.trim().length === 0
              ? 'Write naturally. OptiFlow will show how it interprets every part.'
              : isReady
                ? 'Ready to frame and validate—nothing changes without approval.'
                : 'Add a little more detail so the outcome can be checked.'}
          </span>
          <span className={`shrink-0 text-[10px] font-mono ${isReady ? 'text-ops-emerald' : 'text-ink-muted'}`}>
            {goal.length}/500
          </span>
        </div>
      </div>

      <div className="mt-4">
        <p className="text-[9px] font-mono uppercase tracking-[0.15em] text-ink-muted mb-2.5">
          Use a live-context starting point
        </p>
        <div className="grid sm:grid-cols-3 gap-2">
          {GOAL_STARTERS.map((example) => (
            <button
              key={example.label}
              type="button"
              onClick={() => setGoal(example.text)}
              disabled={loading}
              className="rounded-xl border border-border-dim bg-abyss px-3 py-3 text-left hover:border-ops-amber/40 hover:bg-ops-amber/5 disabled:opacity-40 transition-colors focus-ring"
            >
              <span className="block text-[8px] font-mono uppercase tracking-[0.12em] text-ink-muted">
                {example.signal}
              </span>
              <span className="block text-[11px] font-bold text-ink-secondary mt-1">
                {example.label}
              </span>
            </button>
          ))}
        </div>
      </div>

      {error && (
        <div className="mt-4 rounded-xl border border-ops-rose/30 bg-ops-rose/5 px-4 py-3 text-xs text-ops-rose" role="alert">
          {error}
        </div>
      )}

      <div className="mt-5 flex items-center gap-4">
        <button
          type="submit"
          disabled={!isReady}
          className="group flex-1 rounded-xl bg-ink-primary text-white px-5 py-3.5 text-sm font-bold hover:bg-ops-amber disabled:opacity-30 disabled:cursor-not-allowed transition-all focus-ring flex items-center justify-between"
        >
          <span>{loading ? 'Opening your guided route…' : 'Start today’s guided decision'}</span>
          {loading ? (
            <span className="w-4 h-4 rounded-full border-2 border-white/30 border-t-white animate-spin" />
          ) : (
            <span className="group-hover:translate-x-1 transition-transform">→</span>
          )}
        </button>
        <div className="hidden sm:block text-[10px] leading-relaxed text-ink-muted max-w-[120px]">
          Nothing changes until you approve.
        </div>
      </div>
    </form>
  );
}
