import { useParams, useNavigate } from 'react-router-dom';
import { useRunStatus } from '../hooks/useRunStatus';
import { useRunStream } from '../hooks/useRunStream';
import { EventTimeline } from '../components/run/EventTimeline';
import { PlanWorkspace } from '../components/approval/PlanWorkspace';
import { ClarifyPanel } from '../components/clarification/ClarifyPanel';
import { SummaryPanel } from '../components/completion/SummaryPanel';
import { MissionGuide } from '../components/guide/MissionGuide';
import { getActiveGuide, PHASE_TIMELINE } from '../data/guideContent';
import type { RunStatus } from '../types/api';

const STATUS_BADGE: Record<RunStatus, { label: string; cls: string }> = {
  RECEIVED: { label: 'Route received', cls: 'text-ink-secondary bg-surface' },
  RUNNING: { label: 'In progress', cls: 'text-ops-cyan bg-ops-cyan/10' },
  WAITING_FOR_CLARIFICATION: { label: 'Your input needed', cls: 'text-ops-orange bg-ops-orange/10' },
  WAITING_FOR_APPROVAL: { label: 'Your decision needed', cls: 'text-ops-amber bg-ops-amber/10' },
  EXECUTING: { label: 'Applying decision', cls: 'text-ops-orange bg-ops-orange/10' },
  COMPLETED: { label: 'Route complete', cls: 'text-ops-emerald bg-ops-emerald/10' },
  FAILED: { label: 'Safely stopped', cls: 'text-ops-rose bg-ops-rose/10' },
};

const PHASE_INDEX: Record<string, number> = {
  receive: 0,
  interpret: 1,
  validate: 2,
  clarify: 2,
  evidence: 3,
  optimize: 4,
  approval: 5,
  executing: 6,
  complete: 7,
  failed: 7,
};

function RouteRail({ activeId, failed }: { activeId: string; failed: boolean }) {
  const activeIndex = PHASE_INDEX[activeId] ?? 0;

  return (
    <div className="overflow-x-auto pb-1">
      <div className="min-w-[820px] grid grid-cols-8">
        {PHASE_TIMELINE.map((phase, index) => {
          const done = index < activeIndex || activeId === 'complete';
          const active = index === activeIndex && activeId !== 'complete';
          return (
            <div key={phase.id} className="relative">
              {index < PHASE_TIMELINE.length - 1 && (
                <div className={`absolute top-[15px] left-1/2 right-[-50%] h-0.5 ${index < activeIndex ? 'bg-ops-cyan' : 'bg-border-dim'}`}>
                  {active && <span className="travel-dot absolute -top-[3px] w-2 h-2 rounded-full bg-ops-amber" />}
                </div>
              )}
              <div className="relative z-10 flex flex-col items-center text-center px-1">
                <div className={`w-8 h-8 rounded-full border-2 flex items-center justify-center text-[10px] font-mono font-semibold transition-all ${
                  failed && active
                    ? 'border-ops-rose bg-ops-rose text-white'
                    : active
                      ? 'border-ops-amber bg-ops-amber text-white route-pulse'
                      : done
                        ? 'border-ops-cyan bg-ops-cyan text-white'
                        : 'border-border-dim bg-abyss text-ink-muted'
                }`}>
                  {done ? '✓' : String(index + 1).padStart(2, '0')}
                </div>
                <span className={`text-[9px] font-mono mt-2.5 whitespace-nowrap ${
                  active ? 'text-ink-primary font-semibold' : done ? 'text-ops-cyan' : 'text-ink-muted'
                }`}>
                  {phase.label}
                </span>
              </div>
            </div>
          );
        })}
      </div>
    </div>
  );
}

export function RunCockpitPage() {
  const { runId } = useParams<{ runId: string }>();
  const navigate = useNavigate();
  const { data: runData, error, loading, refetch } = useRunStatus(runId);
  const { events, connected, usingFallback } = useRunStream(runId);

  const status = runData?.status ?? null;
  const badge = status ? STATUS_BADGE[status] : null;
  const guide = getActiveGuide(status, runData?.current_node ?? null);

  const isApproval = status === 'WAITING_FOR_APPROVAL';
  const isClarification = status === 'WAITING_FOR_CLARIFICATION';
  const isTerminal = status === 'COMPLETED' || status === 'FAILED';

  if (!runId) {
    return (
      <div className="min-h-[70vh] flex items-center justify-center text-ink-muted text-sm">
        This route has no run ID.
        <button onClick={() => navigate('/')} className="text-ops-amber ml-2 hover:underline">Start again</button>
      </div>
    );
  }

  if (loading && !runData) {
    return (
      <div className="min-h-[70vh] flex flex-col items-center justify-center gap-5 paper-noise">
        <div className="relative w-14 h-14 rounded-2xl border border-border-base bg-abyss shadow-card flex items-center justify-center">
          <span className="w-5 h-5 rounded-full border-2 border-ops-amber/25 border-t-ops-amber animate-spin" />
        </div>
        <div className="text-center">
          <p className="text-sm font-semibold text-ink-primary">Opening your decision route</p>
          <p className="text-[10px] text-ink-muted font-mono mt-1">#{runId.slice(0, 12)}</p>
        </div>
      </div>
    );
  }

  if (error && !runData) {
    return (
      <div className="min-h-[70vh] flex flex-col items-center justify-center gap-4 text-center px-6">
        <div className="w-12 h-12 rounded-full bg-ops-rose/10 text-ops-rose flex items-center justify-center">!</div>
        <p className="text-sm text-ops-rose">{error}</p>
        <button onClick={() => navigate('/')} className="text-xs font-semibold text-ink-secondary hover:text-ops-amber transition-colors">
          ← Return to the decision canvas
        </button>
      </div>
    );
  }

  return (
    <div className="min-h-full paper-noise">
      <section className="bg-abyss border-b border-border-dim">
        <div className="max-w-[1440px] mx-auto px-5 sm:px-8 pt-6 pb-5">
          <div className="flex flex-col lg:flex-row lg:items-center justify-between gap-4 mb-6">
            <div className="flex flex-wrap items-center gap-3">
              <span className="text-[9px] font-mono uppercase tracking-[0.18em] text-ink-muted">Decision route</span>
              <span className="text-[10px] font-mono text-ink-secondary">#{runId.slice(0, 12)}</span>
              {badge && (
                <span className={`text-[9px] font-mono px-2.5 py-1 rounded-full uppercase tracking-[0.12em] font-semibold ${badge.cls}`}>
                  {badge.label}
                </span>
              )}
            </div>
            <div className="flex items-center gap-2">
              <span className={`relative w-2 h-2 rounded-full ${connected ? 'bg-ops-cyan' : 'bg-ops-orange'}`}>
                <span className="absolute inset-0 rounded-full bg-current animate-ping opacity-30" />
              </span>
              <span className="text-[9px] font-mono uppercase tracking-[0.15em] text-ink-muted">
                {connected ? 'Live updates' : usingFallback ? 'Safe polling' : 'Connecting'}
              </span>
            </div>
          </div>
          <RouteRail activeId={guide.id} failed={status === 'FAILED'} />
        </div>
      </section>

      <div className="max-w-[1440px] mx-auto px-5 sm:px-8 py-6 lg:py-8">
        <div className="grid lg:grid-cols-[minmax(0,1fr)_360px] gap-6 items-start">
          <main className="min-w-0 rounded-[1.5rem] border border-border-dim bg-abyss shadow-card overflow-hidden">
            <div className="px-5 sm:px-7 py-5 border-b border-border-dim flex flex-col sm:flex-row sm:items-center gap-3 justify-between">
              <div>
                <div className="text-[9px] font-mono text-ops-amber uppercase tracking-[0.18em] font-semibold">
                  Now · step {(PHASE_INDEX[guide.id] ?? 0) + 1} of 8
                </div>
                <h1 className="text-xl sm:text-2xl font-extrabold tracking-[-0.04em] mt-1">{guide.label}</h1>
              </div>
              {!isApproval && !isClarification && !isTerminal && (
                <div className="flex items-center gap-2 text-[10px] font-mono text-ink-muted">
                  <span className="w-2 h-2 rounded-full bg-ops-amber animate-pulse" />
                  OptiFlow is working
                </div>
              )}
            </div>

            <div className="p-5 sm:p-7 min-h-[520px]">
              {isApproval ? (
                <PlanWorkspace
                  runId={runId}
                  plans={runData?.candidate_plans ?? []}
                  recommendedPlanId={runData?.recommended_plan_id ?? null}
                  onApproved={refetch}
                />
              ) : isClarification ? (
                <ClarifyPanel runId={runId} runData={runData} onSubmitted={refetch} />
              ) : isTerminal ? (
                <SummaryPanel runData={runData} events={events} />
              ) : (
                <EventTimeline events={events} status={status} connected={connected} usingFallback={usingFallback} />
              )}
            </div>
          </main>

          <aside className="lg:sticky lg:top-24 rounded-[1.5rem] border border-border-dim bg-abyss shadow-card overflow-hidden">
            <MissionGuide status={status} currentNode={runData?.current_node ?? null} />
          </aside>
        </div>
      </div>
    </div>
  );
}
