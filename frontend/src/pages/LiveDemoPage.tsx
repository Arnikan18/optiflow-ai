import { useEffect, useState } from 'react';
import { api } from '../api/client';
import { LiveAIResponsePanel } from '../components/demo/LiveAIResponsePanel';
import { LiveDemoJourneyStrip } from '../components/demo/LiveDemoJourneyStrip';
import {
  LiveEnterpriseEditor,
  type EnterpriseChange,
} from '../components/demo/LiveEnterpriseEditor';
import { PreferenceEngineCard } from '../components/demo/PreferenceEngineCard';
import { JudgeWorkerResponseControl } from '../components/demo/JudgeWorkerResponseControl';
import { useEnterpriseSimulation } from '../hooks/useEnterpriseSimulation';
import { usePreferenceMemory } from '../hooks/usePreferenceMemory';
import type {
  EnterpriseScenario,
  EnterpriseSimulationMode,
  JudgeEnterpriseEventPayload,
  RecentRun,
} from '../types/api';

const STATUS_STYLE = {
  IDLE: 'border-border-base bg-deep text-ink-secondary',
  RUNNING: 'border-ops-emerald/35 bg-ops-emerald/10 text-ops-emerald',
  PAUSED: 'border-ops-orange/35 bg-ops-orange/10 text-ops-orange',
  STOPPED: 'border-border-base bg-deep text-ink-secondary',
  COMPLETED: 'border-ops-cyan/35 bg-ops-cyan/10 text-ops-cyan',
  ERROR: 'border-ops-rose/35 bg-ops-rose/10 text-ops-rose',
} as const;

function formatClock(value: string | null | undefined): string {
  if (!value) return '--:--';
  const date = new Date(value);
  if (Number.isNaN(date.getTime())) return '--:--';
  return new Intl.DateTimeFormat('en-US', {
    hour: '2-digit',
    minute: '2-digit',
    hour12: false,
  }).format(date);
}

function eventText(event: Record<string, unknown>, key: string): string | null {
  const value = event[key];
  return typeof value === 'string' && value.trim() ? value : null;
}

function makeEventIdentity(prefix: string): string {
  const suffix = typeof crypto !== 'undefined' && crypto.randomUUID
    ? crypto.randomUUID().slice(0, 8)
    : `${Date.now()}`;
  return `${prefix}-${suffix}`.toUpperCase();
}

function saveRecentRun(run: RecentRun): void {
  try {
    const current = JSON.parse(localStorage.getItem('optiflow_runs') ?? '[]') as RecentRun[];
    localStorage.setItem(
      'optiflow_runs',
      JSON.stringify([run, ...current.filter((item) => item.run_id !== run.run_id)].slice(0, 20)),
    );
  } catch {
    // Run navigation remains available when browser storage is unavailable.
  }
}

function scenarioProgress(
  scenario: EnterpriseScenario | null,
  currentStage: string | null | undefined,
): number {
  if (!scenario || !currentStage) return 0;
  const index = scenario.stages.indexOf(currentStage);
  return index < 0 ? 0 : index;
}

export function LiveDemoPage() {
  const simulation = useEnterpriseSimulation();
  const preferenceMemory = usePreferenceMemory();
  const [mode, setMode] = useState<EnterpriseSimulationMode>('TIMELINE');
  const [scenarioId, setScenarioId] = useState('');
  const [launchingAI, setLaunchingAI] = useState(false);
  const [activeRunId, setActiveRunId] = useState<string | null>(null);
  const [autoAnalyze, setAutoAnalyze] = useState(true);
  const [aiError, setAIError] = useState<string | null>(null);
  const [lastChange, setLastChange] = useState<EnterpriseChange | null>(null);

  useEffect(() => {
    if (!scenarioId) {
      setScenarioId(
        simulation.status?.scenario_id
        ?? simulation.defaultScenarioId
        ?? simulation.scenarios[0]?.scenario_id
        ?? '',
      );
    }
  }, [
    scenarioId,
    simulation.defaultScenarioId,
    simulation.scenarios,
    simulation.status?.scenario_id,
  ]);

  const scenario = simulation.scenarios.find((item) => item.scenario_id === scenarioId)
    ?? simulation.scenarios.find((item) => item.scenario_id === simulation.status?.scenario_id)
    ?? null;
  const stageIndex = scenarioProgress(scenario, simulation.status?.current_stage);
  const portfolio = simulation.portfolio;
  const simulationStatus = simulation.status?.status ?? 'IDLE';
  const canStart = Boolean(scenarioId);
  const canPause = simulationStatus === 'RUNNING';
  const canResume = simulationStatus === 'PAUSED';
  const canAdvance = mode === 'TIMELINE' && simulationStatus === 'RUNNING';
  const aiStatus = launchingAI
    ? 'Starting analysis'
    : simulation.portfolioDelta
      ? 'Change detected'
      : simulationStatus === 'RUNNING'
        ? 'Monitoring'
        : 'Ready';

  const startAIAnalysis = async (changeLabel?: string) => {
    if (launchingAI) return;
    setLaunchingAI(true);
    setAIError(null);
    try {
      const change = changeLabel
        ?? simulation.status?.current_stage
        ?? 'enterprise';
      const goal = `Protect the highest-pressure customers after the latest ${change} change, while keeping specialist workload within safe available capacity.`;
      const created = await api.createRun(goal);
      saveRecentRun({
        run_id: created.run_id,
        goal_text: goal,
        status: created.status,
        created_at: new Date().toISOString(),
      });
      setActiveRunId(created.run_id);
    } catch (caught: unknown) {
      setAIError(caught instanceof Error ? caught.message : 'The AI analysis could not start.');
    } finally {
      setLaunchingAI(false);
    }
  };

  const advanceTimeline = async () => {
    const changed = await simulation.advance();
    if (changed) {
      setLastChange({
        eventType: 'NEW_TICKET',
        label: 'Timeline event applied',
        description: 'The next prepared enterprise event changed the live baseline.',
        payload: {},
      });
      if (autoAnalyze) {
        await startAIAnalysis('timeline event');
      }
    }
  };

  const applyEnterpriseChange = async (change: EnterpriseChange) => {
    const identity = makeEventIdentity('JUDGE');
    const payload: JudgeEnterpriseEventPayload = {
      event_type: change.eventType,
      event_id: identity,
      idempotency_key: identity.toLowerCase(),
      scenario_id: simulation.status?.scenario_id ?? scenarioId,
      description: change.description,
      payload: change.payload,
    };
    const changed = await simulation.inject(payload);
    if (changed) {
      setLastChange(change);
      if (autoAnalyze) {
        await startAIAnalysis(change.label.toLowerCase());
      }
    }
  };

  return (
    <div className="min-h-full paper-noise">
      <section className="border-b border-border-dim bg-abyss">
        <div className="max-w-[1500px] mx-auto px-5 sm:px-8 py-8 lg:py-10">
          <div>
            <div className="max-w-3xl">
              <div className="flex flex-wrap items-center gap-2">
                <span className="relative w-2.5 h-2.5">
                  <span className="absolute inset-0 rounded-full bg-ops-emerald animate-ping opacity-35" />
                  <span className="absolute inset-0 rounded-full bg-ops-emerald" />
                </span>
                <p className="text-xs font-mono font-bold uppercase tracking-[0.18em] text-ops-emerald">
                  Judge Mode
                </p>
                <span className={`rounded-full border px-3 py-1 text-xs font-mono font-bold ${
                  STATUS_STYLE[simulationStatus]
                }`}>
                  {simulationStatus}
                </span>
              </div>
              <h1 className="text-4xl sm:text-5xl font-extrabold tracking-[-0.055em] leading-[0.98] mt-4">
                Change live data.
                <span className="block text-ops-amber">Test the decision.</span>
              </h1>
              <p className="max-w-2xl text-base text-ink-secondary mt-4">
                Choose one problem or worker, apply a real backend change, and run a fresh governed analysis.
              </p>
            </div>
          </div>
        </div>
      </section>

      <div className="max-w-[1500px] mx-auto px-5 sm:px-8 py-6 lg:py-8 space-y-6">
        {simulation.error && (
          <div className="rounded-2xl border border-ops-rose/30 bg-ops-rose/[0.06] px-5 py-4 flex items-center justify-between gap-4" role="alert">
            <p className="text-sm font-semibold text-ops-rose">{simulation.error}</p>
            <button type="button" onClick={simulation.clearError} className="text-sm font-bold text-ops-rose focus-ring rounded">
              Dismiss
            </button>
          </div>
        )}

        <section className="rounded-[1.5rem] border border-border-dim bg-abyss shadow-card p-5">
          <div className="grid xl:grid-cols-[minmax(260px,1fr)_auto] gap-5 items-end">
            <div className={`grid gap-3 ${mode === 'TIMELINE' ? 'sm:grid-cols-2' : ''}`}>
              <label className="block">
                <span className="text-xs font-mono font-bold uppercase tracking-[0.12em] text-ink-muted">
                  Scenario
                </span>
                <select
                  value={scenarioId}
                  onChange={(event) => setScenarioId(event.target.value)}
                  disabled={simulation.loading}
                  className="mt-2 w-full rounded-xl border border-border-base bg-deep px-4 py-3 text-sm font-bold text-ink-primary focus-ring"
                >
                  {simulation.scenarios.map((item) => (
                    <option key={item.scenario_id} value={item.scenario_id}>{item.name}</option>
                  ))}
                </select>
              </label>
              {mode === 'TIMELINE' && (
                <div>
                  <p className="text-xs font-mono font-bold uppercase tracking-[0.12em] text-ink-muted">
                    Simulation clock
                  </p>
                  <div className="mt-2 rounded-xl border border-border-dim bg-deep px-4 py-2.5 flex items-center justify-between gap-3">
                    <span className="text-2xl font-extrabold text-ink-primary">
                      {formatClock(simulation.status?.current_time)}
                    </span>
                    <span className="text-xs font-mono text-ops-cyan">
                      {simulation.status?.current_stage ?? 'Not started'}
                    </span>
                  </div>
                </div>
              )}
            </div>

            <div className="flex flex-wrap gap-2">
              <button
                type="button"
                disabled={!canStart || simulation.busyAction !== null}
                onClick={() => void simulation.start(scenarioId, mode)}
                className="rounded-xl bg-ink-primary px-4 py-3 text-sm font-bold text-white hover:bg-ops-amber disabled:opacity-40 focus-ring"
              >
                {simulation.busyAction === 'start'
                  ? 'Starting…'
                  : simulationStatus === 'RUNNING'
                    ? 'Restart live demo'
                    : 'Start live demo'}
              </button>
              {mode === 'TIMELINE' && canPause && (
                <button
                  type="button"
                  disabled={simulation.busyAction !== null}
                  onClick={() => void simulation.pause()}
                  className="rounded-xl border border-border-base bg-deep px-4 py-3 text-sm font-bold text-ink-secondary hover:text-ops-orange disabled:opacity-40 focus-ring"
                >
                  Pause
                </button>
              )}
              {mode === 'TIMELINE' && canResume && (
                <button
                  type="button"
                  disabled={simulation.busyAction !== null}
                  onClick={() => void simulation.resume()}
                  className="rounded-xl border border-ops-emerald/35 bg-ops-emerald/[0.06] px-4 py-3 text-sm font-bold text-ops-emerald disabled:opacity-40 focus-ring"
                >
                  Resume
                </button>
              )}
              <button
                type="button"
                disabled={simulation.busyAction !== null}
                onClick={() => void simulation.reset(scenarioId)}
                className="rounded-xl border border-border-base bg-deep px-4 py-3 text-sm font-bold text-ink-secondary hover:text-ops-rose disabled:opacity-40 focus-ring"
              >
                Reset data
              </button>
              {mode === 'TIMELINE' && (
                <button
                  type="button"
                  disabled={!canAdvance || simulation.busyAction !== null}
                  onClick={() => void advanceTimeline()}
                  className="rounded-xl border border-ops-cyan/35 bg-ops-cyan/[0.07] px-4 py-3 text-sm font-bold text-ops-cyan disabled:opacity-35 focus-ring"
                >
                  {simulation.busyAction === 'advance' ? 'Applying event...' : 'Advance one event'}
                </button>
              )}
            </div>
          </div>

          <details className="group mt-4 border-t border-border-dim pt-4">
            <summary className="flex min-h-11 cursor-pointer list-none items-center justify-between gap-3 rounded-xl text-sm font-bold text-ink-secondary focus-ring">
              <span>Advanced scenario controls</span>
              <span className="text-ops-cyan transition-transform group-open:rotate-45">+</span>
            </summary>
            <div className="grid gap-2 pt-3 sm:grid-cols-2">
              {([
                ['INTERACTIVE', 'Free exploration', 'Edit workers and problems directly'],
                ['TIMELINE', 'Timeline testing', 'Advance prepared scenario events'],
              ] as const).map(([value, label, detail]) => (
                <button
                  key={value}
                  type="button"
                  onClick={() => setMode(value)}
                  className={`min-h-14 rounded-xl border px-4 py-3 text-left focus-ring ${
                    mode === value
                      ? 'border-ops-violet/45 bg-ops-violet/[0.08]'
                      : 'border-border-dim bg-deep'
                  }`}
                >
                  <span className={`block text-base font-bold ${
                    mode === value ? 'text-ops-violet' : 'text-ink-primary'
                  }`}>
                    {label}
                  </span>
                  <span className="mt-1 block text-sm text-ink-muted">{detail}</span>
                </button>
              ))}
            </div>
          </details>
        </section>

        <LiveDemoJourneyStrip
          hasPortfolio={Boolean(portfolio)}
          demoStarted={simulationStatus === 'RUNNING'}
          changeDetected={Boolean(simulation.portfolioDelta)}
          analysisStarted={Boolean(activeRunId) || launchingAI}
        />

        <JudgeWorkerResponseControl portfolio={portfolio} />

        {aiError && (
          <div className="rounded-2xl border border-ops-rose/30 bg-ops-rose/[0.06] px-5 py-4 flex items-center justify-between gap-4" role="alert">
            <p className="text-sm font-semibold text-ops-rose">{aiError}</p>
            <button type="button" onClick={() => setAIError(null)} className="text-sm font-bold text-ops-rose focus-ring rounded">
              Dismiss
            </button>
          </div>
        )}

        {activeRunId && (
          <LiveAIResponsePanel
            key={activeRunId}
            runId={activeRunId}
            onClose={() => setActiveRunId(null)}
            onPreferenceUpdated={preferenceMemory.refresh}
          />
        )}

        <div className="grid xl:grid-cols-[minmax(0,1.45fr)_minmax(340px,0.55fr)] gap-5">
          <main className="space-y-5">
            {mode === 'TIMELINE' && (
              <section className="rounded-[1.5rem] border border-border-dim bg-abyss shadow-card p-5 sm:p-6 overflow-hidden">
              <div className="flex flex-wrap items-center justify-between gap-3">
                <div>
                  <p className="text-xs font-mono font-bold uppercase tracking-[0.14em] text-ops-cyan">
                    Enterprise timeline
                  </p>
                  <h2 className="text-2xl font-extrabold tracking-[-0.035em] text-ink-primary mt-1">
                    {scenario?.name ?? 'Choose a scenario'}
                  </h2>
                </div>
                <span className="text-xs font-mono text-ink-muted">
                  {simulation.status?.processed_events.length ?? 0} processed ·{' '}
                  {simulation.status?.pending_events.length ?? 0} waiting
                </span>
              </div>

              <div className="overflow-x-auto mt-6 pb-2">
                <div className="min-w-[760px] relative px-3 py-5">
                  <div className="absolute left-8 right-8 top-[2.15rem] h-1 rounded-full bg-border-dim" />
                  <div
                    className="absolute left-8 top-[2.15rem] h-1 rounded-full bg-ops-cyan transition-all duration-700"
                    style={{
                      width: scenario && scenario.stages.length > 1
                        ? `calc((100% - 4rem) * ${stageIndex / (scenario.stages.length - 1)})`
                        : '0%',
                    }}
                  />
                  <div className="relative flex justify-between gap-4">
                    {(scenario?.stages ?? ['Waiting']).map((stage, index) => {
                      const completed = index < stageIndex;
                      const active = index === stageIndex && simulationStatus !== 'IDLE';
                      return (
                        <div key={stage} className="w-24 text-center">
                          <span className={`relative mx-auto w-9 h-9 rounded-full border-2 flex items-center justify-center text-xs font-mono font-bold transition-all ${
                            completed
                              ? 'border-ops-cyan bg-ops-cyan text-white'
                              : active
                                ? 'border-ops-amber bg-ops-amber text-white shadow-amber-glow route-pulse'
                                : 'border-border-base bg-deep text-ink-muted'
                          }`}>
                            {completed ? '✓' : index + 1}
                          </span>
                          <p className={`text-xs font-bold mt-3 ${active ? 'text-ops-amber' : 'text-ink-secondary'}`}>
                            {stage}
                          </p>
                        </div>
                      );
                    })}
                  </div>
                </div>
              </div>
              </section>
            )}

            {mode === 'INTERACTIVE' && (
              <LiveEnterpriseEditor
                portfolio={portfolio}
                disabled={simulationStatus !== 'RUNNING'}
                busy={simulation.busyAction === 'inject'}
                onApply={applyEnterpriseChange}
              />
            )}

            <section className="rounded-[1.5rem] border border-border-dim bg-abyss shadow-card p-5 sm:p-6">
              <div className="flex items-center justify-between gap-3">
                <div>
                  <p className="text-xs font-mono font-bold uppercase tracking-[0.14em] text-ops-orange">
                    Enterprise changes
                  </p>
                  <h2 className="text-xl font-extrabold text-ink-primary mt-1">What changed</h2>
                </div>
                {simulation.refreshing && <span className="w-4 h-4 rounded-full border-2 border-ops-cyan/25 border-t-ops-cyan animate-spin" />}
              </div>

              <div className="space-y-2 mt-4">
                {simulation.events.slice(0, 3).map((event, index) => {
                  const type = eventText(event, 'event_type') ?? 'ENTERPRISE_EVENT';
                  const description = eventText(event, 'description') ?? type.replace(/_/g, ' ');
                  const processingStatus = eventText(event, 'processing_status') ?? 'RECORDED';
                  const timestamp = eventText(event, 'applied_at') ?? eventText(event, 'created_at');
                  return (
                    <article key={`${eventText(event, 'event_id') ?? type}-${index}`} className="rounded-xl border border-border-dim bg-deep px-4 py-3 flex items-start gap-3">
                      <span className={`mt-1 w-7 h-7 shrink-0 rounded-full flex items-center justify-center text-xs font-bold ${
                        processingStatus.includes('FAIL')
                          ? 'bg-ops-rose/10 text-ops-rose'
                          : 'bg-ops-emerald/10 text-ops-emerald'
                      }`}>
                        {processingStatus.includes('FAIL') ? '!' : '✓'}
                      </span>
                      <div className="min-w-0 flex-1">
                        <div className="flex flex-wrap items-center justify-between gap-2">
                          <p className="text-sm font-bold text-ink-primary">{description}</p>
                          <span className="text-xs font-mono text-ink-muted">{formatClock(timestamp)}</span>
                        </div>
                        <p className="text-xs font-mono text-ops-orange mt-1">{type.replace(/_/g, ' ')}</p>
                      </div>
                    </article>
                  );
                })}
                {simulation.events.length === 0 && (
                  <div className="rounded-xl border border-dashed border-border-base bg-deep/40 px-4 py-8 text-center">
                    <p className="text-sm font-bold text-ink-secondary">No enterprise event has run yet.</p>
                    <p className="text-xs text-ink-muted mt-1">Start the demo, then advance or inject one change.</p>
                  </div>
                )}
              </div>
            </section>
          </main>

          <aside className="space-y-5">
            <section className="rounded-[1.5rem] border border-ops-amber/30 bg-abyss shadow-card p-5">
              <p className="text-xs font-mono font-bold uppercase tracking-[0.14em] text-ops-amber">
                Before → live → AI
              </p>
              <h2 className="mt-1 text-xl font-extrabold text-ink-primary">
                What the decision engine sees
              </h2>
              <div className="flex items-center gap-3 mt-4">
                <span className="relative w-12 h-12 rounded-full border-2 border-ops-amber flex items-center justify-center">
                  {simulationStatus === 'RUNNING' && (
                    <span className="absolute -inset-1.5 rounded-full border border-dashed border-ops-amber/50 animate-spin-slow" />
                  )}
                  <span className="w-3 h-3 rounded-full bg-ops-amber" />
                </span>
                <div>
                  <p className="text-xl font-extrabold text-ink-primary">{aiStatus}</p>
                  <p className="text-sm text-ink-muted mt-1">
                    {activeRunId ? 'Fresh governed route started' : 'Waiting for analysis'}
                  </p>
                </div>
              </div>

              <div className={`mt-4 rounded-xl border px-4 py-3 ${
                lastChange
                  ? 'border-ops-orange/30 bg-ops-orange/[0.06]'
                  : 'border-border-dim bg-deep'
              }`}>
                <p className={`text-sm font-bold ${lastChange ? 'text-ops-orange' : 'text-ink-muted'}`}>
                  {lastChange?.label ?? 'No judge change yet'}
                </p>
                {lastChange && (
                  <p className="mt-1 text-sm text-ink-secondary">{lastChange.description}</p>
                )}
              </div>

              {simulation.portfolioDelta && (
                <div className="rounded-xl border border-ops-orange/25 bg-ops-orange/[0.06] p-4 mt-4">
                  <p className="text-sm font-extrabold text-ops-orange">
                    {simulation.portfolioDelta.incidentIds.length
                      + simulation.portfolioDelta.customerIds.length
                      + simulation.portfolioDelta.specialistIds.length} entities changed
                  </p>
                  <div className="grid grid-cols-2 gap-2 mt-3">
                    <div className="rounded-lg bg-abyss px-3 py-2">
                      <p className="text-xs text-ink-muted">Urgent · before → now</p>
                      <p className="text-lg font-extrabold text-ink-primary">
                        {simulation.portfolioDelta.urgentBefore} → {simulation.portfolioDelta.urgentAfter}
                      </p>
                    </div>
                    <div className="rounded-lg bg-abyss px-3 py-2">
                      <p className="text-xs text-ink-muted">Ready · before → now</p>
                      <p className="text-lg font-extrabold text-ink-primary">
                        {simulation.portfolioDelta.availableBefore} → {simulation.portfolioDelta.availableAfter}
                      </p>
                    </div>
                  </div>
                </div>
              )}

              <button
                type="button"
                disabled={launchingAI || !portfolio}
                onClick={() => void startAIAnalysis()}
                className="mt-4 w-full rounded-xl bg-ink-primary px-4 py-3.5 text-sm font-bold text-white hover:bg-ops-amber disabled:opacity-40 focus-ring"
              >
                {launchingAI
                  ? 'Starting AI route...'
                  : activeRunId
                    ? 'Analyze latest state again'
                    : 'Analyze current enterprise ->'}
              </button>
              <label className="mt-3 flex items-center gap-3 rounded-xl border border-border-dim bg-deep px-3 py-3 cursor-pointer">
                <input
                  type="checkbox"
                  checked={autoAnalyze}
                  onChange={(event) => setAutoAnalyze(event.target.checked)}
                  className="h-4 w-4 accent-amber-500"
                />
                <span>
                  <span className="block text-sm font-bold text-ink-primary">
                    Analyze applied changes
                  </span>
                  <span className="block text-sm text-ink-muted mt-0.5">
                    Starts a fresh governed route after each successful event.
                  </span>
                </span>
              </label>
            </section>

            <PreferenceEngineCard
              data={preferenceMemory.data}
              error={preferenceMemory.error}
              loading={preferenceMemory.loading}
              refreshing={preferenceMemory.refreshing}
              onRefresh={preferenceMemory.refresh}
            />

            <details className="group rounded-[1.5rem] border border-border-dim bg-abyss shadow-card p-5">
              <summary className="flex min-h-11 cursor-pointer list-none items-center justify-between gap-3 text-sm font-bold text-ops-cyan focus-ring rounded-xl">
                <span>Live portfolio totals</span>
                <span className="text-xl transition-transform group-open:rotate-45">+</span>
              </summary>
              <div className="grid grid-cols-2 gap-2 mt-4">
                {[
                  ['Clients', portfolio?.portfolio_summary.total_customers ?? '—'],
                  ['Active', portfolio?.portfolio_summary.total_active_incidents ?? '—'],
                  ['Near SLA', portfolio?.portfolio_summary.incidents_near_sla_breach ?? '—'],
                  ['Team ready', `${portfolio?.portfolio_summary.available_specialists ?? 0}/${portfolio?.portfolio_summary.total_specialists ?? 0}`],
                ].map(([label, value]) => (
                  <div key={label} className="rounded-xl border border-border-dim bg-deep p-3">
                    <p className="text-2xl font-extrabold text-ink-primary">{value}</p>
                    <p className="text-sm text-ink-muted mt-1">{label}</p>
                  </div>
                ))}
              </div>
            </details>

          </aside>
        </div>
      </div>
    </div>
  );
}
