import { useEffect, useMemo, useState } from 'react';
import { Link, useNavigate } from 'react-router-dom';
import { api } from '../api/client';
import type {
  LLMProviderName,
  LLMSettingsPayload,
  LLMSettingsStatus,
  RecentRun,
  RunStatus,
  RunSummary,
} from '../types/api';
import {
  DEFAULT_UI_PREFERENCES,
  readUiPreferences,
  saveUiPreferences,
  type DecisionEngineMode,
  type DetailPreference,
  type MotionPreference,
  type UiPreferences,
  type WalkthroughPace,
} from '../preferences';
import {
  getThemePreference,
  setThemePreference,
  type ThemePreference,
} from '../theme';

type WorkspacePageProps = {
  eyebrow: string;
  title: string;
  description: string;
  purpose: string;
  capabilities: string[];
};

type HistoryView = 'all' | 'attention' | 'moving' | 'closed';

type HistoryRun = RecentRun & {
  summary: RunSummary | null;
  statusError: boolean;
};

const STATUS_GUIDE: Record<RunStatus, {
  label: string;
  group: Exclude<HistoryView, 'all'>;
  next: string;
  explanation: string;
  badge: string;
  marker: string;
}> = {
  RECEIVED: {
    label: 'Route received',
    group: 'moving',
    next: 'Open the route and check whether interpretation has started.',
    explanation: 'Core registered the goal and created its audit identity.',
    badge: 'border-border-base bg-surface text-ink-secondary',
    marker: 'bg-ink-muted',
  },
  RUNNING: {
    label: 'Engines working',
    group: 'moving',
    next: 'Watch the cards arrive; no decision is required yet.',
    explanation: 'OptiFlow is interpreting, checking evidence, or comparing plans.',
    badge: 'border-ops-cyan/25 bg-ops-cyan/10 text-ops-cyan',
    marker: 'bg-ops-cyan',
  },
  WAITING_FOR_CLARIFICATION: {
    label: 'Answer needed',
    group: 'attention',
    next: 'Open the route and answer the unresolved policy question.',
    explanation: 'The system stopped instead of making an important assumption.',
    badge: 'border-ops-orange/30 bg-ops-orange/10 text-ops-orange',
    marker: 'bg-ops-orange',
  },
  WAITING_FOR_APPROVAL: {
    label: 'Decision needed',
    group: 'attention',
    next: 'Compare all plans and approve only the trade-off you accept.',
    explanation: 'Planning is complete and operational writes remain blocked.',
    badge: 'border-ops-amber/30 bg-ops-amber/10 text-ops-amber',
    marker: 'bg-ops-amber',
  },
  EXECUTING: {
    label: 'Applying safely',
    group: 'moving',
    next: 'Open the execution relay to watch each verified hand-off.',
    explanation: 'The approved plan is crossing reversible service boundaries.',
    badge: 'border-ops-orange/30 bg-ops-orange/10 text-ops-orange',
    marker: 'bg-ops-orange',
  },
  REPLANNING: {
    label: 'Finding a safer route',
    group: 'moving',
    next: 'Review which pairing was excluded and wait for replacement plans.',
    explanation: 'A rejection or timeout became a new optimisation constraint.',
    badge: 'border-ops-violet/30 bg-ops-violet/10 text-ops-violet',
    marker: 'bg-ops-violet',
  },
  EXECUTED: {
    label: 'Writes recorded',
    group: 'moving',
    next: 'Wait for Core to close the audit record.',
    explanation: 'The SAGA completed and the final route record is being closed.',
    badge: 'border-ops-cyan/25 bg-ops-cyan/10 text-ops-cyan',
    marker: 'bg-ops-cyan',
  },
  FAILED_SAGA: {
    label: 'Execution review',
    group: 'attention',
    next: 'Inspect the failed boundary and compensation evidence before retrying.',
    explanation: 'The operational transaction stopped before successful completion.',
    badge: 'border-ops-rose/30 bg-ops-rose/10 text-ops-rose',
    marker: 'bg-ops-rose',
  },
  COMPLETED: {
    label: 'Route closed',
    group: 'closed',
    next: 'Reopen the journey to review evidence, trade-offs, and receipts.',
    explanation: 'Core marked the decision route complete and closed its audit record.',
    badge: 'border-ops-emerald/25 bg-ops-emerald/10 text-ops-emerald',
    marker: 'bg-ops-emerald',
  },
  FAILED: {
    label: 'Safely stopped',
    group: 'closed',
    next: 'Review the failure context before deciding whether to try again.',
    explanation: 'The route stopped without claiming a completed decision.',
    badge: 'border-ops-rose/30 bg-ops-rose/10 text-ops-rose',
    marker: 'bg-ops-rose',
  },
  CANCELLED: {
    label: 'Cancelled',
    group: 'closed',
    next: 'Review the record or reuse the goal to start a fresh route.',
    explanation: 'The decision route was intentionally ended.',
    badge: 'border-border-base bg-surface text-ink-secondary',
    marker: 'bg-ink-muted',
  },
};

const HISTORY_VIEWS: { id: HistoryView; label: string; description: string }[] = [
  { id: 'all', label: 'All routes', description: 'Every route saved by this browser' },
  { id: 'attention', label: 'Needs me', description: 'Clarification, approval, or execution review' },
  { id: 'moving', label: 'Moving', description: 'Core is still advancing the route' },
  { id: 'closed', label: 'Closed', description: 'Completed, failed, or cancelled records' },
];

function readHistory(): HistoryRun[] {
  try {
    const saved = JSON.parse(localStorage.getItem('optiflow_runs') ?? '[]') as RecentRun[];
    return saved.map((run) => ({ ...run, summary: null, statusError: false }));
  } catch {
    return [];
  }
}

function formatRunDate(value: string): string {
  const parsed = new Date(value);
  if (Number.isNaN(parsed.getTime())) return 'Date not recorded';
  return new Intl.DateTimeFormat('en-US', {
    month: 'short',
    day: 'numeric',
    hour: '2-digit',
    minute: '2-digit',
  }).format(parsed);
}

function WorkspacePage({
  eyebrow,
  title,
  description,
  purpose,
  capabilities,
}: WorkspacePageProps) {
  return (
    <div className="min-h-full paper-noise">
      <section className="max-w-6xl mx-auto px-5 sm:px-8 py-12 lg:py-20">
        <div className="grid lg:grid-cols-[minmax(0,1fr)_320px] gap-8 lg:gap-16 items-start">
          <div>
            <p className="text-[10px] font-mono font-semibold uppercase tracking-[0.2em] text-ops-cyan">
              {eyebrow}
            </p>
            <h1 className="max-w-3xl text-4xl sm:text-6xl font-extrabold tracking-[-0.06em] leading-[1.02] mt-4">
              {title}
            </h1>
            <p className="max-w-2xl text-base sm:text-lg leading-relaxed text-ink-secondary mt-6">
              {description}
            </p>
          </div>

          <aside className="rounded-[1.75rem] border border-border-base bg-abyss shadow-card overflow-hidden">
            <div className="h-1.5 bg-ops-cyan" />
            <div className="p-6">
              <p className="text-[9px] font-mono uppercase tracking-[0.18em] text-ink-muted">
                Workspace purpose
              </p>
              <p className="text-xl font-extrabold tracking-[-0.04em] text-ink-primary mt-3">
                {purpose}
              </p>
              <ul className="mt-5 space-y-3">
                {capabilities.map((capability) => (
                  <li key={capability} className="flex gap-3 text-sm leading-relaxed text-ink-secondary">
                    <span className="mt-2 w-1.5 h-1.5 shrink-0 rounded-full bg-ops-cyan" />
                    <span>{capability}</span>
                  </li>
                ))}
              </ul>
              <div className="mt-6 pt-5 border-t border-border-dim flex items-center gap-2 text-[10px] font-mono uppercase tracking-[0.14em] text-ops-emerald">
                <span className="w-2 h-2 rounded-full bg-ops-emerald" />
                Connected to Core
              </div>
            </div>
          </aside>
        </div>
      </section>
    </div>
  );
}

export function RunHistoryPage() {
  const navigate = useNavigate();
  const [runs, setRuns] = useState<HistoryRun[]>(readHistory);
  const [activeView, setActiveView] = useState<HistoryView>('all');
  const [refreshing, setRefreshing] = useState(runs.length > 0);

  useEffect(() => {
    if (runs.length === 0) {
      setRefreshing(false);
      return;
    }

    let cancelled = false;
    const refresh = async () => {
      const refreshed = await Promise.all(runs.map(async (run): Promise<HistoryRun> => {
        try {
          const summary = await api.getRunStatus(run.run_id);
          return {
            ...run,
            status: summary.status,
            summary,
            statusError: false,
          };
        } catch {
          return { ...run, summary: null, statusError: true };
        }
      }));

      if (cancelled) return;
      setRuns(refreshed);
      setRefreshing(false);
      try {
        const saved: RecentRun[] = refreshed.map((run) => ({
          run_id: run.run_id,
          goal_text: run.goal_text,
          status: run.status,
          created_at: run.created_at,
        }));
        localStorage.setItem('optiflow_runs', JSON.stringify(saved));
      } catch {
        // Browser history remains useful even when persistence is unavailable.
      }
    };

    void refresh();
    return () => {
      cancelled = true;
    };
    // Refresh the saved snapshot once when the page opens.
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  const counts = useMemo(() => ({
    all: runs.length,
    attention: runs.filter((run) => STATUS_GUIDE[run.status].group === 'attention').length,
    moving: runs.filter((run) => STATUS_GUIDE[run.status].group === 'moving').length,
    closed: runs.filter((run) => STATUS_GUIDE[run.status].group === 'closed').length,
  }), [runs]);

  const visibleRuns = useMemo(
    () => activeView === 'all'
      ? runs
      : runs.filter((run) => STATUS_GUIDE[run.status].group === activeView),
    [activeView, runs],
  );

  const reuseGoal = (goal: string) => {
    try {
      sessionStorage.setItem('optiflow_goal_draft', goal);
    } catch {
      // Navigation still works; the user can copy from the history card.
    }
    navigate('/');
  };

  return (
    <div className="min-h-full paper-noise">
      <section className="border-b border-border-dim bg-abyss">
        <div className="max-w-7xl mx-auto px-5 sm:px-8 py-10 lg:py-14">
          <div className="grid lg:grid-cols-[minmax(0,1fr)_340px] gap-8 items-end">
            <div>
              <p className="text-[9px] font-mono font-semibold uppercase tracking-[0.2em] text-ops-cyan">
                Decision memory
              </p>
              <h1 className="max-w-4xl text-4xl sm:text-6xl font-extrabold tracking-[-0.06em] leading-[0.98] mt-4">
                Every route leaves a
                <span className="block text-ops-cyan">teachable trail.</span>
              </h1>
              <p className="max-w-2xl text-sm sm:text-base leading-relaxed text-ink-secondary mt-5">
                Resume unfinished work, reopen the exact evidence and trade-offs, or reuse an earlier
                goal with today&apos;s portfolio state.
              </p>
            </div>
            <aside className="rounded-2xl border border-border-dim bg-deep p-5">
              <p className="text-[8px] font-mono font-semibold uppercase tracking-[0.16em] text-ink-muted">
                Current history scope
              </p>
              <p className="text-sm font-bold text-ink-primary mt-2">Last 10 routes from this browser</p>
              <p className="text-[10px] leading-relaxed text-ink-muted mt-2">
                Statuses refresh from Core. A backend run-list endpoint is still needed for shared,
                cross-device team history.
              </p>
              <div className="flex items-center gap-2 mt-4 pt-4 border-t border-border-dim text-[9px] font-mono uppercase tracking-[0.12em] text-ops-emerald">
                <span className={`w-2 h-2 rounded-full bg-ops-emerald ${refreshing ? 'animate-pulse' : ''}`} />
                {refreshing ? 'Refreshing from Core' : 'Core status checked'}
              </div>
            </aside>
          </div>
        </div>
      </section>

      <section className="max-w-7xl mx-auto px-5 sm:px-8 py-8 lg:py-10">
        <div className="grid grid-cols-2 lg:grid-cols-4 gap-3" role="tablist" aria-label="History views">
          {HISTORY_VIEWS.map((view) => {
            const active = activeView === view.id;
            return (
              <button
                key={view.id}
                type="button"
                role="tab"
                aria-selected={active}
                onClick={() => setActiveView(view.id)}
                className={`rounded-2xl border p-4 text-left transition-all focus-ring ${
                  active
                    ? 'border-ops-cyan bg-ops-cyan/[0.06] shadow-card'
                    : 'border-border-dim bg-abyss hover:border-border-base'
                }`}
              >
                <div className="flex items-center justify-between gap-3">
                  <span className={`text-[10px] font-bold ${active ? 'text-ops-cyan' : 'text-ink-secondary'}`}>
                    {view.label}
                  </span>
                  <span className="text-xl font-extrabold text-ink-primary">{counts[view.id]}</span>
                </div>
                <p className="hidden sm:block text-[9px] leading-relaxed text-ink-muted mt-2">
                  {view.description}
                </p>
              </button>
            );
          })}
        </div>

        {visibleRuns.length === 0 ? (
          <div className="mt-6 rounded-[1.75rem] border border-dashed border-border-base bg-abyss px-6 py-16 text-center">
            <p className="text-[9px] font-mono uppercase tracking-[0.18em] text-ink-muted">
              {runs.length === 0 ? 'No decision routes yet' : `No ${HISTORY_VIEWS.find((view) => view.id === activeView)?.label.toLowerCase()}`}
            </p>
            <h2 className="text-xl font-extrabold tracking-[-0.035em] text-ink-primary mt-3">
              {runs.length === 0 ? 'Your first trail begins with today’s goal.' : 'Nothing is waiting in this view.'}
            </h2>
            <p className="text-xs leading-relaxed text-ink-muted mt-2">
              {runs.length === 0
                ? 'State the outcome, boundary, and timeframe. OptiFlow will preserve every card here.'
                : 'Choose another history view to inspect the routes saved in this browser.'}
            </p>
            {runs.length === 0 && (
              <Link
                to="/"
                className="inline-flex mt-5 rounded-xl bg-ink-primary px-5 py-3 text-xs font-bold text-white hover:bg-ops-cyan focus-ring"
              >
                Set today&apos;s goal
              </Link>
            )}
          </div>
        ) : (
          <div className="relative mt-7">
            <div className="absolute left-[19px] top-8 bottom-8 w-px bg-border-dim sm:left-[27px]" aria-hidden="true" />
            <div className="space-y-4">
              {visibleRuns.map((run, index) => {
                const guide = STATUS_GUIDE[run.status];
                const planCount = run.summary?.candidate_plans.length ?? 0;
                return (
                  <article
                    key={run.run_id}
                    className="relative grid grid-cols-[40px_minmax(0,1fr)] gap-3 sm:grid-cols-[56px_minmax(0,1fr)] sm:gap-5"
                  >
                    <div className={`relative z-10 mt-6 flex h-10 w-10 items-center justify-center rounded-full border-4 border-void text-[9px] font-mono font-bold text-white sm:h-14 sm:w-14 ${guide.marker}`}>
                      {String(index + 1).padStart(2, '0')}
                    </div>
                    <div className="rounded-[1.5rem] border border-border-dim bg-abyss shadow-card overflow-hidden">
                      <div className={`h-1 ${guide.marker}`} />
                      <div className="p-5 sm:p-6">
                        <div className="flex flex-col sm:flex-row sm:items-start sm:justify-between gap-3">
                          <div>
                            <div className="flex flex-wrap items-center gap-2">
                              <span className="text-[9px] font-mono text-ink-muted">#{run.run_id}</span>
                              <span className={`rounded-full border px-2.5 py-1 text-[8px] font-mono font-semibold uppercase tracking-[0.1em] ${guide.badge}`}>
                                {guide.label}
                              </span>
                              {run.statusError && (
                                <span className="rounded-full border border-ops-orange/25 bg-ops-orange/10 px-2.5 py-1 text-[8px] font-mono text-ops-orange">
                                  saved status
                                </span>
                              )}
                            </div>
                            <p className="mt-2 text-[9px] font-mono text-ink-muted">{formatRunDate(run.created_at)}</p>
                          </div>
                          <div className="flex flex-wrap gap-2">
                            <button
                              type="button"
                              onClick={() => reuseGoal(run.goal_text)}
                              className="rounded-lg border border-border-base bg-deep px-3 py-2 text-[9px] font-semibold text-ink-secondary hover:text-ops-cyan focus-ring"
                            >
                              Use goal again
                            </button>
                            <Link
                              to={`/run/${run.run_id}`}
                              className="rounded-lg bg-ink-primary px-3 py-2 text-[9px] font-bold text-white hover:bg-ops-cyan focus-ring"
                            >
                              Open exact route &rarr;
                            </Link>
                          </div>
                        </div>

                        <h2 className="max-w-4xl text-base sm:text-lg font-extrabold leading-snug tracking-[-0.025em] text-ink-primary mt-5">
                          {run.goal_text}
                        </h2>

                        <div className="grid md:grid-cols-2 gap-3 mt-5">
                          <div className="rounded-xl border border-border-dim bg-deep/55 p-4">
                            <p className="text-[8px] font-mono font-semibold uppercase tracking-[0.14em] text-ink-muted">
                              What this status means
                            </p>
                            <p className="text-[11px] leading-relaxed text-ink-secondary mt-2">
                              {guide.explanation}
                            </p>
                          </div>
                          <div className="rounded-xl border border-ops-cyan/20 bg-ops-cyan/[0.04] p-4">
                            <p className="text-[8px] font-mono font-semibold uppercase tracking-[0.14em] text-ops-cyan">
                              Your next sensible move
                            </p>
                            <p className="text-[11px] leading-relaxed text-ink-secondary mt-2">
                              {guide.next}
                            </p>
                          </div>
                        </div>

                        {run.summary && (
                          <div className="flex flex-wrap gap-x-5 gap-y-2 mt-4 pt-4 border-t border-border-dim text-[9px] font-mono text-ink-muted">
                            <span>{planCount} candidate {planCount === 1 ? 'plan' : 'plans'}</span>
                            <span>{run.summary.replan_count} replans</span>
                            <span>{run.summary.excluded_specialist_incidents.length} blocked pairings</span>
                            <span>current card: {run.summary.current_node?.replace(/_/g, ' ') ?? 'not reported'}</span>
                          </div>
                        )}
                      </div>
                    </div>
                  </article>
                );
              })}
            </div>
          </div>
        )}
      </section>
    </div>
  );
}

export { DemoLabPage } from './DemoLabPage';

const THEME_OPTIONS: { id: ThemePreference; label: string; description: string }[] = [
  { id: 'light', label: 'Light', description: 'Bright paper workspace for daylight use.' },
  { id: 'dark', label: 'Dark', description: 'Low-glare operations room appearance.' },
  { id: 'system', label: 'System', description: 'Follow this device automatically.' },
];

const PACE_OPTIONS: { id: WalkthroughPace; label: string; value: string; description: string }[] = [
  { id: 'focused', label: 'Focused', value: '1.6 seconds', description: 'Faster review for experienced operators.' },
  { id: 'standard', label: 'Standard', value: '2.6 seconds', description: 'Recommended teaching pace for most users.' },
  { id: 'deliberate', label: 'Deliberate', value: '4.0 seconds', description: 'Extra reading time between arriving cards.' },
];

const PROVIDER_MODELS: Record<string, string[]> = {
  gemini: [
    'gemini-3.6-flash',
    'gemini-3.5-flash',
    'gemini-3.5-flash-lite',
    'gemini-3.1-flash-lite',
    'gemini-2.5-flash',
    'gemini-2.5-flash-lite',
    'gemini-2.5-pro',
  ],
  groq: [
    'llama-3.1-8b-instant',
    'llama-3.3-70b-versatile',
    'openai/gpt-oss-20b',
    'openai/gpt-oss-120b',
  ],
};

interface KeyDraft {
  label: string;
  apiKey: string;
}

export function SettingsPage() {
  const [theme, setTheme] = useState<ThemePreference>(getThemePreference);
  const [preferences, setPreferences] = useState<UiPreferences>(readUiPreferences);
  const [provider, setProvider] = useState<LLMProviderName>('gemini');
  const [providerModels, setProviderModels] = useState(PROVIDER_MODELS);
  const [model, setModel] = useState(PROVIDER_MODELS.gemini[0]);
  const [keys, setKeys] = useState<KeyDraft[]>([
    { label: 'Primary', apiKey: '' },
    { label: 'Backup 1', apiKey: '' },
    { label: 'Backup 2', apiKey: '' },
  ]);
  const [endpointAvailable, setEndpointAvailable] = useState<boolean | null>(null);
  const [connectionMessage, setConnectionMessage] = useState<string | null>(null);
  const [connectionError, setConnectionError] = useState<string | null>(null);
  const [connectionBusy, setConnectionBusy] = useState<'test' | 'save' | null>(null);
  const [settingsStatus, setSettingsStatus] = useState<LLMSettingsStatus | null>(null);

  useEffect(() => {
    const updateTheme = (event: Event) => {
      setTheme((event as CustomEvent<ThemePreference>).detail);
    };
    window.addEventListener('optiflow:theme-change', updateTheme);
    return () => window.removeEventListener('optiflow:theme-change', updateTheme);
  }, []);

  useEffect(() => {
    let cancelled = false;
    const probe = async () => {
      try {
        const [catalog, status] = await Promise.all([
          api.getLLMModels(),
          api.getLLMSettings(),
        ]);
        if (cancelled) return;
        const models = Object.fromEntries(
          catalog.providers.map((entry) => [entry.id, entry.models]),
        ) as Record<LLMProviderName, string[]>;
        setProviderModels(models);
        setSettingsStatus(status);
        setEndpointAvailable(true);
        const selectedProvider = status.active_llm_provider
          ?? catalog.providers[0]?.id
          ?? 'gemini';
        setProvider(selectedProvider);
        setModel(
          status.providers[selectedProvider]?.model_name
            ?? catalog.providers.find((entry) => entry.id === selectedProvider)?.default_model
            ?? models[selectedProvider][0],
        );
        const nextPreferences = {
          ...readUiPreferences(),
          decisionEngine: status.mode,
        };
        setPreferences(nextPreferences);
        saveUiPreferences(nextPreferences);
      } catch {
        if (!cancelled) setEndpointAvailable(false);
      }
    };
    void probe();
    return () => {
      cancelled = true;
    };
  }, []);

  const updatePreference = <Key extends keyof UiPreferences>(
    key: Key,
    value: UiPreferences[Key],
  ) => {
    const next = { ...preferences, [key]: value };
    setPreferences(next);
    saveUiPreferences(next);
  };

  const updateProvider = (nextProvider: LLMProviderName) => {
    setProvider(nextProvider);
    setModel(
      settingsStatus?.providers[nextProvider]?.model_name
        ?? providerModels[nextProvider][0],
    );
    setConnectionMessage(null);
    setConnectionError(null);
  };

  const updateKey = (index: number, value: string) => {
    setKeys((current) => current.map((entry, entryIndex) =>
      entryIndex === index ? { ...entry, apiKey: value } : entry));
  };

  const submitConnection = async (action: 'test' | 'save') => {
    setConnectionBusy(action);
    setConnectionMessage(null);
    setConnectionError(null);
    try {
      const credentials = keys
        .filter((entry) => entry.apiKey.trim())
        .map((entry, priority) => ({
          label: entry.label,
          api_key: entry.apiKey.trim(),
          priority,
        }));
      if (credentials.length === 0) throw new Error('Enter at least one provider API key.');

      const payload: LLMSettingsPayload = {
        version: 1,
        mode: 'ai_assisted',
        active_llm_provider: provider,
        providers: {
          [provider]: {
            model_name: model,
            credentials,
          },
        },
      };
      const result = action === 'test'
        ? await api.testLLMSettings(payload)
        : await api.saveLLMSettings(payload);
      if (!result.connected) {
        throw new Error(result.credentials
          .filter((entry) => !entry.connected)
          .map((entry) => `${entry.label}: ${entry.message}`)
          .join(' '));
      }
      setConnectionMessage(action === 'test'
        ? `Connection verified with ${result.credentials.length} credential${result.credentials.length === 1 ? '' : 's'}. Nothing was saved.`
        : `${provider === 'gemini' ? 'Google Gemini' : 'GroqCloud'} is connected. Core encrypted and saved ${result.credentials.length} credential${result.credentials.length === 1 ? '' : 's'}.`);
      if (action === 'save') {
        setKeys((current) => current.map((entry) => ({ ...entry, apiKey: '' })));
        const status = await api.getLLMSettings();
        setSettingsStatus(status);
        updatePreference('decisionEngine', 'ai_assisted');
      }
    } catch (error: unknown) {
      setConnectionError(error instanceof Error ? error.message : 'The secure settings request failed.');
    } finally {
      setConnectionBusy(null);
    }
  };

  const disconnectProvider = async () => {
    setConnectionBusy('save');
    setConnectionMessage(null);
    setConnectionError(null);
    try {
      const status = await api.disconnectLLM(null);
      setSettingsStatus(status);
      updatePreference('decisionEngine', 'rules_only');
      setConnectionMessage('Core is now using the deterministic rules-only engine. Saved provider credentials were removed.');
    } catch (error: unknown) {
      setConnectionError(error instanceof Error ? error.message : 'Core could not switch to rules-only mode.');
    } finally {
      setConnectionBusy(null);
    }
  };

  const selectDecisionEngine = (mode: DecisionEngineMode) => {
    setConnectionMessage(null);
    setConnectionError(null);
    if (mode === 'rules_only' && settingsStatus?.mode === 'ai_assisted') {
      setConnectionError('Core is currently AI-assisted. Choose “Switch Core to rules-only” below to remove saved credentials safely.');
      return;
    }
    updatePreference('decisionEngine', mode);
  };

  const resetPersonalization = () => {
    setThemePreference('system');
    setTheme('system');
    setPreferences(DEFAULT_UI_PREFERENCES);
    saveUiPreferences(DEFAULT_UI_PREFERENCES);
  };

  return (
    <div className="min-h-full paper-noise">
      <section className="border-b border-border-dim bg-abyss">
        <div className="max-w-7xl mx-auto px-5 sm:px-8 py-10 lg:py-14">
          <div className="flex flex-col lg:flex-row lg:items-end lg:justify-between gap-7">
            <div>
              <p className="text-[9px] font-mono font-semibold uppercase tracking-[0.2em] text-ops-amber">
                Personal operating rules
              </p>
              <h1 className="max-w-4xl text-4xl sm:text-6xl font-extrabold tracking-[-0.06em] leading-[0.98] mt-4">
                Adjust the experience.
                <span className="block text-ops-amber">Keep the decision truth.</span>
              </h1>
              <p className="max-w-2xl text-sm sm:text-base leading-relaxed text-ink-secondary mt-5">
                Appearance and teaching pace are personal. Evidence, approval gates, and audit records
                remain visible regardless of these choices.
              </p>
            </div>
            <button
              type="button"
              onClick={resetPersonalization}
              className="self-start rounded-xl border border-border-base bg-deep px-4 py-3 text-[10px] font-bold text-ink-secondary hover:text-ops-amber focus-ring"
            >
              Restore recommended settings
            </button>
          </div>
        </div>
      </section>

      <section className="max-w-7xl mx-auto px-5 sm:px-8 py-8 lg:py-10 space-y-6">
        <article className="rounded-[1.5rem] border border-border-dim bg-abyss shadow-card overflow-hidden">
          <div className="h-1 bg-ops-cyan" />
          <div className="p-5 sm:p-7">
            <p className="text-[8px] font-mono font-semibold uppercase tracking-[0.16em] text-ops-cyan">
              Appearance
            </p>
            <h2 className="text-xl font-extrabold tracking-[-0.035em] mt-2">Choose how the workspace feels.</h2>
            <div className="grid sm:grid-cols-3 gap-3 mt-5">
              {THEME_OPTIONS.map((option) => (
                <button
                  key={option.id}
                  type="button"
                  aria-pressed={theme === option.id}
                  onClick={() => {
                    setThemePreference(option.id);
                    setTheme(option.id);
                  }}
                  className={`rounded-2xl border p-5 text-left transition-all focus-ring ${
                    theme === option.id
                      ? 'border-ops-cyan bg-ops-cyan/[0.055] shadow-card'
                      : 'border-border-dim bg-deep/45 hover:border-border-base'
                  }`}
                >
                  <div className="flex items-center justify-between gap-3">
                    <span className="text-sm font-bold text-ink-primary">{option.label}</span>
                    <span className={`h-4 w-4 rounded-full border-4 ${
                      theme === option.id ? 'border-ops-cyan bg-abyss' : 'border-border-base'
                    }`} />
                  </div>
                  <p className="text-[10px] leading-relaxed text-ink-muted mt-2">{option.description}</p>
                </button>
              ))}
            </div>
          </div>
        </article>

        <article className="rounded-[1.5rem] border border-border-dim bg-abyss shadow-card overflow-hidden">
          <div className="h-1 bg-ops-violet" />
          <div className="p-5 sm:p-7">
            <p className="text-[8px] font-mono font-semibold uppercase tracking-[0.16em] text-ops-violet">
              Guided walkthrough
            </p>
            <h2 className="text-xl font-extrabold tracking-[-0.035em] mt-2">Set a pace you can understand.</h2>
            <div className="grid sm:grid-cols-3 gap-3 mt-5">
              {PACE_OPTIONS.map((option) => (
                <button
                  key={option.id}
                  type="button"
                  aria-pressed={preferences.walkthroughPace === option.id}
                  onClick={() => updatePreference('walkthroughPace', option.id)}
                  className={`rounded-2xl border p-5 text-left transition-all focus-ring ${
                    preferences.walkthroughPace === option.id
                      ? 'border-ops-violet bg-ops-violet/[0.055]'
                      : 'border-border-dim bg-deep/45 hover:border-border-base'
                  }`}
                >
                  <p className="text-sm font-bold text-ink-primary">{option.label}</p>
                  <p className="text-[9px] font-mono text-ops-violet mt-1">{option.value}</p>
                  <p className="text-[10px] leading-relaxed text-ink-muted mt-2">{option.description}</p>
                </button>
              ))}
            </div>

            <div className="grid md:grid-cols-2 gap-4 mt-5">
              <fieldset className="rounded-2xl border border-border-dim bg-deep/45 p-5">
                <legend className="px-1 text-[8px] font-mono font-semibold uppercase tracking-[0.14em] text-ink-muted">Motion</legend>
                {([
                  ['system', 'Follow device', 'Use the operating system motion preference.'],
                  ['reduced', 'Always reduce motion', 'Short dwell and nearly instant transitions.'],
                ] as [MotionPreference, string, string][]).map(([id, label, description]) => (
                  <label key={id} className="flex gap-3 py-2.5 cursor-pointer">
                    <input
                      type="radio"
                      name="motion"
                      checked={preferences.motion === id}
                      onChange={() => updatePreference('motion', id)}
                      className="mt-1 accent-current"
                    />
                    <span>
                      <span className="block text-xs font-bold text-ink-primary">{label}</span>
                      <span className="block text-[10px] leading-relaxed text-ink-muted mt-1">{description}</span>
                    </span>
                  </label>
                ))}
              </fieldset>
              <fieldset className="rounded-2xl border border-border-dim bg-deep/45 p-5">
                <legend className="px-1 text-[8px] font-mono font-semibold uppercase tracking-[0.14em] text-ink-muted">Teaching detail</legend>
                {([
                  ['guided', 'Guided', 'Show definitions, checks, and manual fallback teaching.'],
                  ['compact', 'Compact', 'Keep evidence visible with shorter supporting explanations.'],
                ] as [DetailPreference, string, string][]).map(([id, label, description]) => (
                  <label key={id} className="flex gap-3 py-2.5 cursor-pointer">
                    <input
                      type="radio"
                      name="detail"
                      checked={preferences.detail === id}
                      onChange={() => updatePreference('detail', id)}
                      className="mt-1 accent-current"
                    />
                    <span>
                      <span className="block text-xs font-bold text-ink-primary">{label}</span>
                      <span className="block text-[10px] leading-relaxed text-ink-muted mt-1">{description}</span>
                    </span>
                  </label>
                ))}
              </fieldset>
            </div>
          </div>
        </article>

        <article className="rounded-[1.5rem] border border-border-dim bg-abyss shadow-card overflow-hidden">
          <div className="h-1 bg-ops-amber" />
          <div className="p-5 sm:p-7">
            <div className="flex flex-col lg:flex-row lg:items-start lg:justify-between gap-4">
              <div>
                <p className="text-[8px] font-mono font-semibold uppercase tracking-[0.16em] text-ops-amber">
                  Decision engine
                </p>
                <h2 className="text-xl font-extrabold tracking-[-0.035em] mt-2">Choose rules-only or AI-assisted explanation.</h2>
              </div>
              <span className="rounded-full border border-ops-emerald/25 bg-ops-emerald/[0.055] px-3 py-2 text-[8px] font-mono font-semibold uppercase tracking-[0.12em] text-ops-emerald">
                Optimisation remains deterministic
              </span>
            </div>

            <div className="grid md:grid-cols-2 gap-3 mt-5">
              {([
                ['rules_only', 'Rules-only', 'No external LLM required. Goal interpretation and explanations use deterministic fallback logic.'],
                ['ai_assisted', 'AI-assisted', 'Use a configured provider for language interpretation and explanations; approval rules do not change.'],
              ] as [DecisionEngineMode, string, string][]).map(([id, label, description]) => (
                <button
                  key={id}
                  type="button"
                  aria-pressed={preferences.decisionEngine === id}
                  onClick={() => selectDecisionEngine(id)}
                  className={`rounded-2xl border p-5 text-left focus-ring ${
                    preferences.decisionEngine === id
                      ? 'border-ops-amber bg-ops-amber/[0.055]'
                      : 'border-border-dim bg-deep/45 hover:border-border-base'
                  }`}
                >
                  <p className="text-sm font-bold text-ink-primary">{label}</p>
                  <p className="text-[10px] leading-relaxed text-ink-muted mt-2">{description}</p>
                </button>
              ))}
            </div>

            {preferences.decisionEngine === 'ai_assisted' && (
              <div className="mt-5 rounded-2xl border border-border-base bg-deep/55 p-5 sm:p-6">
                <div className="flex flex-col sm:flex-row sm:items-center sm:justify-between gap-3">
                  <div>
                    <p className="text-[8px] font-mono font-semibold uppercase tracking-[0.14em] text-ink-muted">Secure provider connection</p>
                    <p className="text-xs text-ink-secondary mt-1.5">
                      Enter only provider keys. Core authorization stays in the server proxy, and provider keys move directly to encrypted Core storage.
                    </p>
                  </div>
                  <span className={`rounded-full border px-3 py-1.5 text-[8px] font-mono font-semibold uppercase tracking-[0.1em] ${
                    endpointAvailable
                      ? 'border-ops-emerald/25 bg-ops-emerald/10 text-ops-emerald'
                      : 'border-ops-orange/25 bg-ops-orange/10 text-ops-orange'
                  }`}>
                    {endpointAvailable === null
                      ? 'Checking Core'
                      : endpointAvailable
                        ? 'Secure endpoint ready'
                        : 'Core unreachable'}
                  </span>
                </div>

                <div className="grid sm:grid-cols-2 gap-3 mt-5">
                  {(['gemini', 'groq'] as const).map((id) => (
                    <button
                      key={id}
                      type="button"
                      aria-pressed={provider === id}
                      onClick={() => updateProvider(id)}
                      className={`rounded-xl border p-4 text-left focus-ring ${
                        provider === id ? 'border-ops-amber bg-abyss' : 'border-border-dim bg-deep'
                      }`}
                    >
                      <p className="text-xs font-bold text-ink-primary">{id === 'gemini' ? 'Google Gemini' : 'GroqCloud'}</p>
                      <p className="text-[9px] text-ink-muted mt-1">{providerModels[id].length} supported production models</p>
                    </button>
                  ))}
                </div>

                <label className="block mt-4">
                  <span className="text-[9px] font-mono font-semibold uppercase tracking-[0.12em] text-ink-muted">Model</span>
                  <select
                    value={model}
                    onChange={(event) => setModel(event.target.value)}
                    className="mt-2 w-full rounded-xl border border-border-base bg-abyss px-4 py-3 text-xs text-ink-primary focus-ring"
                  >
                    {providerModels[provider].map((modelName) => (
                      <option key={modelName} value={modelName}>{modelName}</option>
                    ))}
                  </select>
                </label>

                <div className="grid lg:grid-cols-3 gap-3 mt-4">
                  {keys.map((entry, index) => (
                    <label key={entry.label} className="block">
                      <span className="text-[9px] font-mono font-semibold uppercase tracking-[0.12em] text-ink-muted">
                        {entry.label} key
                      </span>
                      <input
                        type="password"
                        autoComplete="off"
                        value={entry.apiKey}
                        onChange={(event) => updateKey(index, event.target.value)}
                        placeholder={index === 0 ? 'Required' : 'Optional failover'}
                        className="mt-2 w-full rounded-xl border border-border-base bg-abyss px-4 py-3 text-xs text-ink-primary placeholder:text-ink-ghost focus-ring"
                      />
                    </label>
                  ))}
                </div>
                <p className="text-[9px] leading-relaxed text-ink-muted mt-3">
                  Core tries keys in priority order only for retryable quota, authentication, or provider-availability failures.
                  It does not switch models silently.
                </p>

                {settingsStatus?.active_llm_provider && (
                  <div className="mt-4 rounded-xl border border-ops-emerald/20 bg-ops-emerald/[0.045] p-4">
                    <p className="text-[9px] font-mono font-semibold uppercase tracking-[0.12em] text-ops-emerald">
                      Core runtime · {settingsStatus.active_llm_provider} · {settingsStatus.providers[settingsStatus.active_llm_provider]?.model_name}
                    </p>
                    <div className="flex flex-wrap gap-2 mt-2">
                      {settingsStatus.providers[settingsStatus.active_llm_provider]?.credentials.map((credential) => (
                        <span
                          key={`${credential.label}-${credential.priority}`}
                          className="rounded-full border border-border-base bg-abyss px-3 py-1.5 text-[8px] text-ink-secondary"
                        >
                          {credential.label} {credential.masked_key}
                        </span>
                      ))}
                    </div>
                  </div>
                )}

                {!endpointAvailable && endpointAvailable !== null && (
                  <div className="mt-4 rounded-xl border border-ops-orange/25 bg-ops-orange/[0.055] p-4">
                    <p className="text-[10px] font-bold text-ops-orange">Core settings API is unreachable.</p>
                    <p className="text-[9px] leading-relaxed text-ink-muted mt-1.5">
                      Start or restart Core API on port 8000. Rules-only decisions remain available while provider controls stay disabled.
                    </p>
                  </div>
                )}
                {connectionError && <p className="mt-4 text-[10px] text-ops-rose" role="alert">{connectionError}</p>}
                {connectionMessage && <p className="mt-4 text-[10px] text-ops-emerald" role="status">{connectionMessage}</p>}

                <div className="flex flex-wrap gap-2 mt-5">
                  <button
                    type="button"
                    disabled={!endpointAvailable || connectionBusy !== null}
                    onClick={() => void submitConnection('test')}
                    className="rounded-xl border border-border-base bg-abyss px-4 py-3 text-[10px] font-bold text-ink-secondary hover:text-ops-amber disabled:opacity-40 focus-ring"
                  >
                    {connectionBusy === 'test' ? 'Testing…' : 'Test without saving'}
                  </button>
                  <button
                    type="button"
                    disabled={!endpointAvailable || connectionBusy !== null}
                    onClick={() => void submitConnection('save')}
                    className="rounded-xl bg-ink-primary px-4 py-3 text-[10px] font-bold text-white hover:bg-ops-amber disabled:opacity-40 focus-ring"
                  >
                    {connectionBusy === 'save' ? 'Encrypting and saving…' : 'Connect provider'}
                  </button>
                  {settingsStatus?.mode === 'ai_assisted' && (
                    <button
                      type="button"
                      disabled={!endpointAvailable || connectionBusy !== null}
                      onClick={() => void disconnectProvider()}
                      className="rounded-xl border border-ops-rose/25 bg-ops-rose/[0.045] px-4 py-3 text-[10px] font-bold text-ops-rose hover:bg-ops-rose/10 disabled:opacity-40 focus-ring"
                    >
                      Switch Core to rules-only
                    </button>
                  )}
                </div>
              </div>
            )}
          </div>
        </article>
      </section>
    </div>
  );
}
