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
  COLD_START: 'Learning you',
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

function formatDecision(decision: RecentPreferenceDecision): {
  title: string;
  detail: string;
  tone: string;
} {
  const chosen = profileLabel(decision.selected_profile);
  const suggested = profileLabel(decision.personalized_profile);

  if (decision.decision === 'REJECTED') {
    return {
      title: 'Rejected all proposed plans',
      detail: decision.personalized_profile
        ? `AI suggested ${suggested}; no plan was executed.`
        : 'No plan was executed.',
      tone: 'bg-ops-rose/10 text-ops-rose',
    };
  }
  if (decision.accepted_personalized === true) {
    return {
      title: `Accepted ${chosen}`,
      detail: 'Matched the personalized recommendation.',
      tone: 'bg-ops-emerald/10 text-ops-emerald',
    };
  }
  if (decision.accepted_personalized === false && decision.selected_profile) {
    return {
      title: `Preferred ${chosen}`,
      detail: `Overrode the AI suggestion of ${suggested}.`,
      tone: 'bg-ops-violet/10 text-ops-violet',
    };
  }
  return {
    title: decision.selected_profile ? `Selected ${chosen}` : decision.decision,
    detail: 'This choice is now part of preference memory.',
    tone: 'bg-ops-cyan/10 text-ops-cyan',
  };
}

function shortDate(value: string): string {
  const parsed = new Date(value);
  if (Number.isNaN(parsed.getTime())) return 'Recently';
  return new Intl.DateTimeFormat('en-US', {
    month: 'short',
    day: 'numeric',
    hour: '2-digit',
    minute: '2-digit',
  }).format(parsed);
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
    <section className="rounded-[1.5rem] border border-ops-violet/30 bg-abyss shadow-card overflow-hidden">
      <header className="p-5 border-b border-border-dim flex items-start justify-between gap-4">
        <div className="flex items-center gap-4">
          <div className="relative w-14 h-14 shrink-0 rounded-full border-2 border-ops-violet/50 flex items-center justify-center">
            <span className="absolute -inset-1.5 rounded-full border border-dashed border-ops-violet/45 animate-spin-slow" />
            <span className="absolute inset-2 rounded-full border border-ops-cyan/45 animate-pulse" />
            <span className="w-3 h-3 rounded-full bg-ops-violet" />
          </div>
          <div>
            <p className="text-sm font-mono font-bold uppercase tracking-[0.12em] text-ops-violet">
              Preference engine
            </p>
            <h2 className="text-2xl font-extrabold tracking-[-0.035em] text-ink-primary mt-1">
              It remembers your choices
            </h2>
          </div>
        </div>
        {data && (
          <span className={`rounded-full border px-3 py-1.5 text-sm font-bold ${
            STATE_STYLES[data.learning_state]
          }`}>
            {STATE_LABELS[data.learning_state]}
          </span>
        )}
      </header>

      <div className="p-5 space-y-5">
        {loading && !data && (
          <div className="rounded-2xl border border-border-dim bg-deep p-7 text-center">
            <span className="mx-auto block w-6 h-6 rounded-full border-2 border-ops-violet/25 border-t-ops-violet animate-spin" />
            <p className="text-base font-bold text-ink-secondary mt-3">
              Loading decision memory
            </p>
          </div>
        )}

        {error && !data && (
          <div className="rounded-2xl border border-ops-rose/30 bg-ops-rose/[0.06] p-5">
            <p className="text-base font-bold text-ops-rose">Memory is unavailable</p>
            <p className="text-sm text-ink-secondary mt-2">{error}</p>
            <button
              type="button"
              onClick={() => void onRefresh()}
              className="mt-4 rounded-xl bg-ink-primary px-4 py-2.5 text-sm font-bold text-white focus-ring"
            >
              Try again
            </button>
          </div>
        )}

        {data && (
          <>
            <div className="grid sm:grid-cols-[minmax(0,1fr)_auto] gap-4 items-center rounded-2xl border border-border-dim bg-deep p-4">
              <div>
                <p className="text-sm font-semibold text-ink-muted">Current learned preference</p>
                <p className="text-3xl font-extrabold text-ink-primary mt-1">
                  {profileLabel(data.dominant_profile)}
                </p>
                <p className="text-sm leading-relaxed text-ink-secondary mt-2">
                  {data.learning_state === 'COLD_START'
                    ? `${data.runs_until_next_state} more decisions before personalization can influence recommendations.`
                    : `${Math.round(data.dominant_profile_share * 100)}% of selected plans follow this strategy.`}
                </p>
              </div>
              <div className="grid grid-cols-2 gap-2 sm:min-w-[230px]">
                <div className="rounded-xl bg-abyss p-3">
                  <p className="text-2xl font-extrabold text-ink-primary">{data.total_decisions}</p>
                  <p className="text-sm text-ink-muted">decisions learned</p>
                </div>
                <div className="rounded-xl bg-abyss p-3">
                  <p className="text-2xl font-extrabold text-ink-primary">
                    {Math.round(data.confidence * 100)}%
                  </p>
                  <p className="text-sm text-ink-muted">confidence</p>
                </div>
              </div>
            </div>

            <div>
              <div className="flex items-center justify-between gap-3">
                <p className="text-base font-extrabold text-ink-primary">
                  Learning progress
                </p>
                <span className="text-sm font-mono text-ink-muted">
                  {data.learning_state === 'MATURE'
                    ? 'Ready'
                    : `${data.runs_until_next_state} to next stage`}
                </span>
              </div>
              <div className="h-2.5 rounded-full bg-border-dim overflow-hidden mt-3">
                <div
                  className="h-full rounded-full bg-gradient-to-r from-ops-cyan via-ops-violet to-ops-emerald transition-all duration-700"
                  style={{ width: `${progress}%` }}
                />
              </div>
            </div>

            <div>
              <p className="text-base font-extrabold text-ink-primary">Strategy pattern</p>
              <div className="space-y-3 mt-3">
                {Object.entries(data.profile_counts).map(([profile, count]) => {
                  const share = totalSelections > 0 ? (count / totalSelections) * 100 : 0;
                  const dominant = profile === data.dominant_profile;
                  return (
                    <div key={profile}>
                      <div className="flex items-center justify-between gap-3 text-sm">
                        <span className={dominant ? 'font-bold text-ops-violet' : 'text-ink-secondary'}>
                          {profileLabel(profile)}
                        </span>
                        <span className="font-mono text-ink-muted">{count}</span>
                      </div>
                      <div className="h-2 rounded-full bg-border-dim overflow-hidden mt-1.5">
                        <div
                          className={`h-full rounded-full transition-all duration-700 ${
                            dominant ? 'bg-ops-violet' : 'bg-ops-cyan/60'
                          }`}
                          style={{ width: `${share}%` }}
                        />
                      </div>
                    </div>
                  );
                })}
              </div>
            </div>

            <div>
              <div className="flex items-center justify-between gap-3">
                <div>
                  <p className="text-base font-extrabold text-ink-primary">
                    Your recent decisions
                  </p>
                  <p className="text-sm text-ink-muted mt-1">
                    Persisted by Core and reused in future recommendations.
                  </p>
                </div>
                {refreshing && (
                  <span className="w-5 h-5 rounded-full border-2 border-ops-violet/25 border-t-ops-violet animate-spin" />
                )}
              </div>

              <div className="space-y-2 mt-3">
                {data.recent_decisions.map((decision) => {
                  const presentation = formatDecision(decision);
                  return (
                    <article
                      key={decision.event_id}
                      className="rounded-xl border border-border-dim bg-deep p-4"
                    >
                      <div className="flex items-start gap-3">
                        <span className={`mt-0.5 w-8 h-8 shrink-0 rounded-full flex items-center justify-center font-bold ${presentation.tone}`}>
                          {decision.decision === 'REJECTED' ? '!' : '✓'}
                        </span>
                        <div className="min-w-0 flex-1">
                          <div className="flex flex-wrap items-center justify-between gap-2">
                            <p className="text-base font-bold text-ink-primary">
                              {presentation.title}
                            </p>
                            <span className="text-sm font-mono text-ink-muted">
                              {shortDate(decision.created_at)}
                            </span>
                          </div>
                          <p className="text-sm text-ink-secondary mt-1">
                            {presentation.detail}
                          </p>
                        </div>
                      </div>
                    </article>
                  );
                })}

                {data.recent_decisions.length === 0 && (
                  <div className="rounded-xl border border-dashed border-border-base bg-deep/40 p-6 text-center">
                    <p className="text-base font-bold text-ink-secondary">
                      No decisions recorded yet
                    </p>
                    <p className="text-sm text-ink-muted mt-1">
                      Approve, override, or reject a plan to teach the engine.
                    </p>
                  </div>
                )}
              </div>
            </div>

            {data.learned_constraints.length > 0 && (
              <details className="rounded-xl border border-border-dim bg-deep">
                <summary className="cursor-pointer list-none px-4 py-3 text-base font-bold text-ink-primary focus-ring rounded-xl">
                  Remembered goal constraints ({data.learned_constraints.length})
                </summary>
                <ul className="border-t border-border-dim p-4 space-y-2">
                  {data.learned_constraints.map((constraint) => (
                    <li key={constraint} className="text-sm text-ink-secondary">
                      {constraint}
                    </li>
                  ))}
                </ul>
              </details>
            )}
          </>
        )}
      </div>
    </section>
  );
}
