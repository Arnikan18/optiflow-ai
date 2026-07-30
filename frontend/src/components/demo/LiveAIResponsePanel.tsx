import { useEffect } from 'react';
import { Link } from 'react-router-dom';
import { PlanWorkspace } from '../approval/PlanWorkspace';
import { useRunStatus } from '../../hooks/useRunStatus';
import { useRunStream } from '../../hooks/useRunStream';
import type { RunStatus } from '../../types/api';

interface LiveAIResponsePanelProps {
  runId: string;
  onClose: () => void;
  onPreferenceUpdated?: () => void;
}

const STATUS_LABEL: Record<RunStatus, string> = {
  RECEIVED: 'Goal received',
  RUNNING: 'Reading live evidence',
  WAITING_FOR_CLARIFICATION: 'Human context needed',
  WAITING_FOR_APPROVAL: 'Decision ready',
  EXECUTING: 'Applying approved plan',
  REPLANNING: 'Re-evaluating',
  EXECUTED: 'Changes applied',
  FAILED_SAGA: 'Execution recovered',
  COMPLETED: 'Decision complete',
  FAILED: 'Safely stopped',
  CANCELLED: 'Cancelled',
};

const ROUTE_STEPS = [
  { label: 'Observe', detail: 'Live tools' },
  { label: 'Evaluate', detail: 'Evidence + constraints' },
  { label: 'Compare', detail: 'Candidate plans' },
  { label: 'Decide', detail: 'Human gate' },
  { label: 'Act', detail: 'Verified writes' },
] as const;

function routeIndex(status: RunStatus | undefined, node: string | null | undefined): number {
  if (!status) return 0;
  if (['EXECUTING', 'EXECUTED', 'FAILED_SAGA', 'COMPLETED'].includes(status)) return 4;
  if (status === 'WAITING_FOR_APPROVAL') return 3;
  if (status === 'REPLANNING') return 2;
  if (status === 'WAITING_FOR_CLARIFICATION') return 1;

  const normalized = node?.toLowerCase() ?? '';
  if (
    normalized.includes('candidate')
    || normalized.includes('optimi')
    || normalized.includes('recommend')
    || normalized.includes('plan')
  ) return 2;
  if (
    normalized.includes('evidence')
    || normalized.includes('tool')
    || normalized.includes('state')
  ) return 1;
  return 0;
}

function readableSummary(value: string | Record<string, unknown> | null | undefined): string | null {
  if (!value) return null;
  if (typeof value === 'string') return value;

  for (const key of ['summary', 'message', 'outcome', 'decision']) {
    const item = value[key];
    if (typeof item === 'string' && item.trim()) return item;
  }
  return null;
}

export function LiveAIResponsePanel({
  runId,
  onClose,
  onPreferenceUpdated,
}: LiveAIResponsePanelProps) {
  const { data, error, loading, refetch } = useRunStatus(runId);
  const { events, connected, usingFallback } = useRunStream(runId);
  const preferenceUpdateCount = events.filter(
    (event) => event.event_type === 'PREFERENCE_MEM_UPDATED',
  ).length;
  const activeIndex = routeIndex(data?.status, data?.current_node);
  const latestEvent = events.at(-1);
  const outcome = readableSummary(data?.change_summary)
    ?? readableSummary(data?.business_summary);
  const isTerminal = data
    ? ['COMPLETED', 'FAILED', 'CANCELLED', 'FAILED_SAGA'].includes(data.status)
    : false;

  useEffect(() => {
    if (preferenceUpdateCount > 0) {
      onPreferenceUpdated?.();
    }
  }, [onPreferenceUpdated, preferenceUpdateCount]);

  return (
    <section
      className="rounded-[1.75rem] border border-ops-amber/35 bg-abyss shadow-card overflow-hidden animate-fade-up"
      aria-live="polite"
    >
      <header className="border-b border-border-dim px-5 sm:px-7 py-5 flex flex-col sm:flex-row sm:items-center justify-between gap-4">
        <div>
          <div className="flex flex-wrap items-center gap-2">
            <span className="relative w-2.5 h-2.5 rounded-full bg-ops-amber">
              {!isTerminal && (
                <span className="absolute inset-0 rounded-full bg-ops-amber animate-ping opacity-35" />
              )}
            </span>
            <p className="text-xs font-mono font-bold uppercase tracking-[0.16em] text-ops-amber">
              AI response to the live change
            </p>
            <span className="rounded-full bg-deep px-2.5 py-1 text-xs font-mono text-ink-muted">
              #{runId.slice(0, 12)}
            </span>
          </div>
          <h2 className="text-2xl font-extrabold tracking-[-0.04em] text-ink-primary mt-2">
            {data ? STATUS_LABEL[data.status] : 'Opening decision route'}
          </h2>
        </div>
        <div className="flex flex-wrap items-center gap-2">
          <span className="text-xs font-mono text-ink-muted">
            {connected ? 'Live events' : usingFallback ? 'Safe polling' : 'Connecting'}
          </span>
          <Link
            to={`/run/${encodeURIComponent(runId)}`}
            className="rounded-xl border border-border-base bg-deep px-4 py-2.5 text-sm font-bold text-ink-secondary hover:text-ops-amber focus-ring"
          >
            Open full decision map
          </Link>
          <button
            type="button"
            onClick={onClose}
            className="rounded-xl border border-border-base bg-deep px-3 py-2.5 text-sm font-bold text-ink-muted hover:text-ink-primary focus-ring"
            aria-label="Close AI response"
          >
            Close
          </button>
        </div>
      </header>

      <div className="p-5 sm:p-7">
        {error && !data ? (
          <div className="rounded-2xl border border-ops-rose/30 bg-ops-rose/[0.06] p-5">
            <p className="text-sm font-bold text-ops-rose">The analysis route could not be read.</p>
            <p className="text-sm text-ink-secondary mt-2">{error}</p>
            <button
              type="button"
              onClick={() => void refetch()}
              className="mt-4 rounded-xl bg-ink-primary px-4 py-2.5 text-sm font-bold text-white focus-ring"
            >
              Try again
            </button>
          </div>
        ) : (
          <>
            <div className="grid grid-cols-5 gap-2" aria-label="Decision route progress">
              {ROUTE_STEPS.map((step, index) => {
                const complete = index < activeIndex || (isTerminal && index <= activeIndex);
                const active = index === activeIndex && !isTerminal;
                return (
                  <div key={step.label} className="min-w-0">
                    <div className={`h-1.5 rounded-full transition-colors duration-500 ${
                      complete
                        ? 'bg-ops-emerald'
                        : active
                          ? 'bg-ops-amber route-pulse'
                          : 'bg-border-dim'
                    }`} />
                    <p className={`text-xs sm:text-sm font-extrabold mt-2 ${
                      complete ? 'text-ops-emerald' : active ? 'text-ops-amber' : 'text-ink-muted'
                    }`}>
                      {step.label}
                    </p>
                    <p className="hidden sm:block text-xs text-ink-muted mt-0.5">{step.detail}</p>
                  </div>
                );
              })}
            </div>

            {loading && !data && (
              <div className="rounded-2xl border border-border-dim bg-deep px-5 py-8 text-center mt-6">
                <span className="mx-auto block w-6 h-6 rounded-full border-2 border-ops-amber/25 border-t-ops-amber animate-spin" />
                <p className="text-sm font-bold text-ink-secondary mt-3">Reading the changed enterprise</p>
              </div>
            )}

            {data && data.status !== 'WAITING_FOR_APPROVAL' && (
              <div className="grid sm:grid-cols-[minmax(0,1fr)_auto] gap-4 items-center rounded-2xl border border-border-dim bg-deep p-5 mt-6">
                <div>
                  <p className="text-xs font-mono font-bold uppercase tracking-[0.12em] text-ops-cyan">
                    Now
                  </p>
                  <p className="text-lg font-extrabold text-ink-primary mt-1">
                    {latestEvent?.summary
                      ?? data.current_node?.replace(/_/g, ' ')
                      ?? STATUS_LABEL[data.status]}
                  </p>
                  <p className="text-sm leading-relaxed text-ink-muted mt-2">
                    {outcome
                      ?? 'The governed route is collecting evidence, comparing options, and preserving the human approval gate.'}
                  </p>
                </div>
                <div className="grid grid-cols-2 gap-2 sm:min-w-[220px]">
                  <div className="rounded-xl bg-abyss p-3">
                    <p className="text-2xl font-extrabold text-ink-primary">{events.length}</p>
                    <p className="text-xs text-ink-muted">route events</p>
                  </div>
                  <div className="rounded-xl bg-abyss p-3">
                    <p className="text-2xl font-extrabold text-ink-primary">
                      {data.replan_count}
                    </p>
                    <p className="text-xs text-ink-muted">replans</p>
                  </div>
                </div>
              </div>
            )}

            {data?.status === 'WAITING_FOR_APPROVAL' && (
              <div className="mt-7">
                <PlanWorkspace
                  runId={runId}
                  plans={data.candidate_plans}
                  recommendedPlanId={data.recommended_plan_id}
                  candidatePlanSummary={data.candidate_plan_summary}
                  onApproved={refetch}
                />
              </div>
            )}

            {data?.status === 'WAITING_FOR_CLARIFICATION' && (
              <div className="rounded-2xl border border-ops-orange/30 bg-ops-orange/[0.06] p-5 mt-6">
                <p className="text-lg font-extrabold text-ink-primary">The AI needs human context.</p>
                <p className="text-sm text-ink-secondary mt-2">
                  Open the full decision map to answer the clarification without guessing.
                </p>
                <Link
                  to={`/run/${encodeURIComponent(runId)}`}
                  className="inline-flex mt-4 rounded-xl bg-ops-orange px-4 py-2.5 text-sm font-bold text-white focus-ring"
                >
                  Answer clarification
                </Link>
              </div>
            )}
          </>
        )}
      </div>
    </section>
  );
}
