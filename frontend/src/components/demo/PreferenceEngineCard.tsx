import type {
  PreferenceLearningState,
  PreferenceSummary,
  RecentPreferenceDecision,
} from '../../types/api';

interface PreferenceEngineCardProps {
  data: PreferenceSummary | null;
  error: string | null;
  loading: boolean;
  refreshing: boolean;
  onRefresh: () => Promise<void>;
}

const PROFILE_LABELS: Record<string, string> = {
  BALANCED: 'Balanced',
  SLA_FIRST: 'SLA First',
  REVENUE_FIRST: 'Revenue First',
  FAIRNESS_FIRST: 'Fairness First',
};

const STATE_LABELS: Record<PreferenceLearningState, string> = {
  COLD_START: 'Learning',
  LEARNING: 'Pattern forming',
  MATURE: 'Personalized',
};

const STATE_STYLES: Record<PreferenceLearningState, string> = {
  COLD_START: 'border-ops-cyan/35 bg-ops-cyan/10 text-ops-cyan',
  LEARNING: 'border-ops-violet/35 bg-ops-violet/10 text-ops-violet',
  MATURE: 'border-ops-emerald/35 bg-ops-emerald/10 text-ops-emerald',
};

function profileLabel(value: string | null): string {
  if (!value) return 'No preference yet';
  const normalized = value.trim().toUpperCase().replace(/[- ]/g, '_');
  return PROFILE_LABELS[normalized]
    ?? value.replace(/_/g, ' ').replace(/\b\w/g, (letter) => letter.toUpperCase());
}

function decisionLabel(decision: RecentPreferenceDecision): string {
  if (decision.decision === 'REJECTED') return 'Rejected all plans';
  if (decision.selected_profile) return `${decision.decision === 'APPROVED' ? 'Selected' : 'Preferred'} ${profileLabel(decision.selected_profile)}`;
  return decision.decision;
}

function shortDate(value: string): string {
  const parsed = new Date(value);
  if (Number.isNaN(parsed.getTime())) return 'Recently';
  return new Intl.DateTimeFormat('en-US', {
    month: 'short',
    day: 'numeric',
  }).format(parsed);
}

function Chevron() {
  return (
    <svg viewBox="0 0 20 20" fill="none" stroke="currentColor" strokeWidth="1.8" className="h-5 w-5 transition-transform group-open:rotate-180">
      <path d="m5 7.5 5 5 5-5" />
    </svg>
  );
}

export function PreferenceEngineCard({
  data,
  error,
  loading,
  refreshing,
  onRefresh,
}: PreferenceEngineCardProps) {
  const totalSelections = data
    ? Object.values(data.profile_counts).reduce((sum, count) => sum + count, 0)
    : 0;
  const learningTarget = data?.learning_state === 'COLD_START'
    ? data.cold_start_runs_required
    : data?.mature_runs_required ?? 1;
  const progress = data?.learning_state === 'MATURE'
    ? 100
    : Math.min(100, ((data?.total_decisions ?? 0) / learningTarget) * 100);

  return (
    <section className="overflow-hidden rounded-2xl border border-ops-violet/30 bg-abyss shadow-card">
      <header className="flex items-center justify-between gap-3 border-b border-border-dim p-4">
        <div className="flex min-w-0 items-center gap-3">
          <span className="relative flex h-10 w-10 shrink-0 items-center justify-center rounded-full border border-ops-violet/50">
            <span className="absolute -inset-1 animate-spin-slow rounded-full border border-dashed border-ops-violet/35" />
            <span className="h-2.5 w-2.5 rounded-full bg-ops-violet" />
          </span>
          <div className="min-w-0">
            <p className="text-xs font-bold uppercase tracking-[0.13em] text-ops-violet">Preference memory</p>
            <h2 className="mt-0.5 truncate text-lg font-extrabold text-ink-primary">Learns from your choices</h2>
          </div>
        </div>
        {data && (
          <span className={`shrink-0 rounded-full border px-2.5 py-1 text-xs font-bold ${STATE_STYLES[data.learning_state]}`}>
            {STATE_LABELS[data.learning_state]}
          </span>
        )}
      </header>

      <div className="p-4">
        {loading && !data && (
          <div className="flex items-center justify-center gap-3 rounded-xl bg-deep p-5">
            <span className="h-5 w-5 animate-spin rounded-full border-2 border-ops-violet/25 border-t-ops-violet" />
            <p className="text-sm font-bold text-ink-secondary">Loading memory</p>
          </div>
        )}

        {error && !data && (
          <div className="rounded-xl border border-ops-rose/30 bg-ops-rose/[0.06] p-4">
            <p className="text-sm font-bold text-ops-rose">Memory unavailable</p>
            <button
              type="button"
              onClick={() => void onRefresh()}
              className="mt-3 rounded-lg border border-ops-rose/30 px-3 py-2 text-sm font-bold text-ops-rose focus-ring"
            >
              Try again
            </button>
          </div>
        )}

        {data && (
          <>
            <div className="rounded-xl border border-border-dim bg-deep p-4">
              <p className="text-xs text-ink-muted">Current learned preference</p>
              <p className="mt-1 text-2xl font-extrabold tracking-[-0.035em] text-ink-primary">
                {profileLabel(data.dominant_profile)}
              </p>

              <div className="mt-4 grid grid-cols-2 gap-2">
                <div className="rounded-lg bg-abyss px-3 py-2.5">
                  <p className="text-xl font-extrabold text-ink-primary">{data.total_decisions}</p>
                  <p className="text-xs text-ink-muted">decisions</p>
                </div>
                <div className="rounded-lg bg-abyss px-3 py-2.5">
                  <p className="text-xl font-extrabold text-ink-primary">{Math.round(data.confidence * 100)}%</p>
                  <p className="text-xs text-ink-muted">confidence</p>
                </div>
              </div>

              <div className="mt-4 flex items-center justify-between gap-3 text-xs">
                <span className="font-bold text-ink-secondary">Learning progress</span>
                <span className="text-ink-muted">
                  {data.learning_state === 'MATURE' ? 'Ready' : `${data.runs_until_next_state} to next stage`}
                </span>
              </div>
              <div className="mt-2 h-2 overflow-hidden rounded-full bg-border-dim">
                <div
                  className="h-full rounded-full bg-gradient-to-r from-ops-cyan via-ops-violet to-ops-emerald transition-all duration-700"
                  style={{ width: `${progress}%` }}
                />
              </div>
            </div>

            <details className="group mt-3 rounded-xl border border-border-dim bg-deep">
              <summary className="flex cursor-pointer list-none items-center justify-between gap-3 rounded-xl px-4 py-3 text-sm font-bold text-ink-primary focus-ring">
                <span>View memory details</span>
                <div className="flex items-center gap-2">
                  {refreshing && <span className="h-4 w-4 animate-spin rounded-full border-2 border-ops-violet/25 border-t-ops-violet" />}
                  <Chevron />
                </div>
              </summary>

              <div className="space-y-5 border-t border-border-dim p-4">
                <div>
                  <p className="text-xs font-bold uppercase tracking-[0.12em] text-ink-muted">Strategy pattern</p>
                  <div className="mt-3 space-y-3">
                    {Object.entries(data.profile_counts).map(([profile, count]) => {
                      const share = totalSelections > 0 ? (count / totalSelections) * 100 : 0;
                      const dominant = profile === data.dominant_profile;
                      return (
                        <div key={profile}>
                          <div className="flex items-center justify-between gap-3 text-sm">
                            <span className={dominant ? 'font-bold text-ops-violet' : 'text-ink-secondary'}>
                              {profileLabel(profile)}
                            </span>
                            <span className="text-xs text-ink-muted">{count}</span>
                          </div>
                          <div className="mt-1.5 h-1.5 overflow-hidden rounded-full bg-border-dim">
                            <div
                              className={`h-full rounded-full ${dominant ? 'bg-ops-violet' : 'bg-ops-cyan/60'}`}
                              style={{ width: `${share}%` }}
                            />
                          </div>
                        </div>
                      );
                    })}
                  </div>
                </div>

                <div>
                  <p className="text-xs font-bold uppercase tracking-[0.12em] text-ink-muted">Recent decisions</p>
                  <div className="mt-3 space-y-2">
                    {data.recent_decisions.map((decision) => (
                      <article key={decision.event_id} className="flex items-center justify-between gap-3 rounded-lg bg-abyss px-3 py-2.5">
                        <div className="min-w-0">
                          <p className="truncate text-sm font-bold text-ink-primary">{decisionLabel(decision)}</p>
                          <p className="mt-0.5 text-xs text-ink-muted">
                            {decision.accepted_personalized === true
                              ? 'Matched recommendation'
                              : decision.accepted_personalized === false
                                ? 'Manager override'
                                : 'Stored in memory'}
                          </p>
                        </div>
                        <span className="shrink-0 text-xs text-ink-muted">{shortDate(decision.created_at)}</span>
                      </article>
                    ))}
                    {data.recent_decisions.length === 0 && (
                      <p className="rounded-lg bg-abyss px-3 py-4 text-center text-sm text-ink-muted">
                        No decisions recorded yet.
                      </p>
                    )}
                  </div>
                </div>

                {data.learned_constraints.length > 0 && (
                  <div>
                    <p className="text-xs font-bold uppercase tracking-[0.12em] text-ink-muted">Remembered constraints</p>
                    <div className="mt-2 flex flex-wrap gap-2">
                      {data.learned_constraints.map((constraint) => (
                        <span key={constraint} className="rounded-full border border-border-base bg-abyss px-2.5 py-1 text-xs text-ink-secondary">
                          {constraint}
                        </span>
                      ))}
                    </div>
                  </div>
                )}
              </div>
            </details>
          </>
        )}
      </div>
    </section>
  );
}
