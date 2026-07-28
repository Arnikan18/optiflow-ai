import { useState } from 'react';
import { useNavigate } from 'react-router-dom';
import { api } from '../../api/client';
import type { RecentRun } from '../../types/api';

const DEMO_GOALS = [
  {
    label: 'Protect revenue',
    text: 'Optimize scheduling to protect high-ARR customers and balance workload fairly.',
  },
  {
    label: 'Protect SLA',
    text: 'Assign available specialists to critical SLA incidents, prioritising Tier 1 customers.',
  },
  {
    label: 'Protect team',
    text: 'Rebalance specialist workload to prevent burnout while maintaining SLA coverage.',
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

export function GoalInput() {
  const [goal, setGoal] = useState('');
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const navigate = useNavigate();
  const isReady = goal.trim().length >= 10 && !loading;

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
      <div className="rounded-2xl border border-border-base bg-deep overflow-hidden focus-within:border-ops-amber focus-within:ring-4 focus-within:ring-ops-amber/10 transition-all">
        <label htmlFor="decision-goal" className="sr-only">Decision goal</label>
        <textarea
          id="decision-goal"
          value={goal}
          onChange={(event) => setGoal(event.target.value)}
          placeholder="Example: Protect Tier 1 customers from SLA breach while keeping team workload fair."
          rows={4}
          disabled={loading}
          className="w-full bg-transparent p-4 sm:p-5 pb-3 text-ink-primary placeholder:text-ink-muted resize-none focus:outline-none text-sm leading-relaxed disabled:opacity-50"
        />
        <div className="px-4 sm:px-5 py-3 border-t border-border-dim flex items-center justify-between gap-3">
          <span className="text-[10px] font-mono uppercase tracking-[0.13em] text-ink-muted">
            Include priority + limits + timeframe
          </span>
          <span className={`text-[10px] font-mono ${isReady ? 'text-ops-emerald' : 'text-ink-muted'}`}>
            {goal.length}/500
          </span>
        </div>
      </div>

      <div className="mt-4">
        <p className="text-[10px] font-mono uppercase tracking-[0.14em] text-ink-muted mb-2.5">Or choose a starting point</p>
        <div className="flex flex-wrap gap-2">
          {DEMO_GOALS.map((example) => (
            <button
              key={example.label}
              type="button"
              onClick={() => setGoal(example.text)}
              className="px-3 py-2 rounded-full border border-border-dim bg-abyss text-[11px] font-semibold text-ink-secondary hover:text-ops-amber hover:border-ops-amber/40 transition-colors focus-ring"
            >
              {example.label}
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
          <span>{loading ? 'Building your route…' : 'Build my decision route'}</span>
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
