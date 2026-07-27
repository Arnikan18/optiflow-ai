import { useState } from 'react';
import { useNavigate } from 'react-router-dom';
import { api } from '../../api/client';
import type { RecentRun } from '../../types/api';

const DEMO_GOALS = [
  'Optimize scheduling to protect high-ARR customers and balance workload fairly.',
  'Assign available specialists to critical SLA incidents, prioritising Tier 1 customers.',
  'Rebalance specialist workload to prevent burnout while maintaining SLA coverage.',
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
    const updated = [entry, ...existing].slice(0, 10);
    localStorage.setItem('optiflow_runs', JSON.stringify(updated));
  } catch {
    // localStorage may be unavailable
  }
}

export function GoalInput() {
  const [goal, setGoal] = useState('');
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const navigate = useNavigate();

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    const trimmed = goal.trim();
    if (trimmed.length < 10) return;

    setLoading(true);
    setError(null);

    try {
      const { run_id } = await api.createRun(trimmed);
      saveRecentRun(run_id, trimmed);
      navigate(`/run/${run_id}`);
    } catch (err: unknown) {
      const msg = err instanceof Error ? err.message : 'Failed to initiate run';
      setError(msg);
      setLoading(false);
    }
  };

  const charCount = goal.length;
  const isReady = goal.trim().length >= 10 && !loading;

  return (
    <form onSubmit={handleSubmit} className="space-y-5">
      {/* Label */}
      <div className="flex items-center justify-between">
        <label className="text-xs font-mono text-ink-secondary uppercase tracking-widest">
          Decision Goal
        </label>
        <span className="text-xs font-mono text-ink-muted">{charCount} chars</span>
      </div>

      {/* Textarea */}
      <div className="relative">
        <textarea
          value={goal}
          onChange={(e) => setGoal(e.target.value)}
          placeholder="Describe your operational objective in plain English…&#10;&#10;e.g. 'Optimise scheduling to protect high-ARR customers and balance workload fairly.'"
          rows={6}
          disabled={loading}
          className="w-full bg-deep border border-border-dim rounded-lg p-4 text-ink-primary
            placeholder:text-ink-ghost resize-none focus:outline-none focus:border-ops-amber
            font-sans text-sm leading-relaxed transition-colors duration-200
            disabled:opacity-50 disabled:cursor-not-allowed"
        />
        {/* Bottom-right decorative corner */}
        <div className="absolute bottom-2 right-2 text-xs font-mono text-ink-ghost pointer-events-none">
          {isReady ? '▶ READY' : ''}
        </div>
      </div>

      {/* Example goals */}
      <div>
        <p className="text-xs font-mono text-ink-muted uppercase tracking-widest mb-2">
          Quick-start examples
        </p>
        <div className="space-y-2">
          {DEMO_GOALS.map((g, i) => (
            <button
              key={i}
              type="button"
              onClick={() => setGoal(g)}
              className="w-full text-left text-xs text-ink-secondary bg-abyss border border-border-dim
                rounded-lg px-3 py-2.5 hover:border-ops-amber/60 hover:text-ink-primary
                hover:bg-ops-amber/5 transition-all duration-200 font-mono leading-relaxed"
            >
              <span className="text-ops-amber mr-2">{i + 1}.</span>{g}
            </button>
          ))}
        </div>
      </div>

      {/* Error */}
      {error && (
        <div className="flex items-start gap-3 bg-ops-rose/8 border border-ops-rose/40 rounded-lg px-4 py-3 animate-fade-up">
          <span className="text-ops-rose text-sm shrink-0">✗</span>
          <p className="text-sm text-ops-rose leading-relaxed">{error}</p>
        </div>
      )}

      {/* Submit */}
      <button
        type="submit"
        disabled={!isReady}
        className="w-full bg-ops-amber text-void font-bold py-3.5 px-6 rounded-lg
          hover:bg-ops-amber-bright disabled:opacity-30 disabled:cursor-not-allowed
          transition-all duration-200 text-sm tracking-widest uppercase flex items-center justify-center gap-3
          glow-amber focus:outline-none focus:ring-2 focus:ring-ops-amber/50"
      >
        {loading ? (
          <>
            <span className="w-4 h-4 border-2 border-void/30 border-t-void rounded-full animate-spin" />
            Initiating Run…
          </>
        ) : (
          'Initiate Run →'
        )}
      </button>
    </form>
  );
}
