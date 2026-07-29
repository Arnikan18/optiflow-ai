import { useState } from 'react';
import { useParams, useNavigate } from 'react-router-dom';
import { useRunStatus } from '../hooks/useRunStatus';
import { useRunStream } from '../hooks/useRunStream';
import { EventTimeline } from '../components/run/EventTimeline';
import { PlaybackControls } from '../components/run/PlaybackControls';
import {
  DecisionJourneyRail,
  normalizeJourneyStage,
} from '../components/run/DecisionJourneyRail';
import { PlanWorkspace } from '../components/approval/PlanWorkspace';
import { ClarifyPanel } from '../components/clarification/ClarifyPanel';
import { SummaryPanel } from '../components/completion/SummaryPanel';
import { MissionGuide } from '../components/guide/MissionGuide';
import { getActiveGuide, PHASE_GUIDES } from '../data/guideContent';
import { useGuidedPlayback } from '../hooks/useGuidedPlayback';
import type { RecentRun, RunStatus } from '../types/api';

const STATUS_BADGE: Record<RunStatus, { label: string; cls: string }> = {
  RECEIVED: { label: 'Route received', cls: 'text-ink-secondary bg-surface' },
  RUNNING: { label: 'In progress', cls: 'text-ops-cyan bg-ops-cyan/10' },
  WAITING_FOR_CLARIFICATION: { label: 'Your input needed', cls: 'text-ops-orange bg-ops-orange/10' },
  WAITING_FOR_APPROVAL: { label: 'Your decision needed', cls: 'text-ops-amber bg-ops-amber/10' },
  EXECUTING: { label: 'Applying decision', cls: 'text-ops-orange bg-ops-orange/10' },
  REPLANNING: { label: 'Replanning route', cls: 'text-ops-violet bg-ops-violet/10' },
  EXECUTED: { label: 'Execution complete', cls: 'text-ops-cyan bg-ops-cyan/10' },
  FAILED_SAGA: { label: 'Execution recovered', cls: 'text-ops-rose bg-ops-rose/10' },
  COMPLETED: { label: 'Route complete', cls: 'text-ops-emerald bg-ops-emerald/10' },
  FAILED: { label: 'Safely stopped', cls: 'text-ops-rose bg-ops-rose/10' },
  CANCELLED: { label: 'Cancelled', cls: 'text-ink-secondary bg-surface' },
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

function readSavedGoal(runId: string): string | null {
  try {
    const runs = JSON.parse(localStorage.getItem('optiflow_runs') ?? '[]') as RecentRun[];
    return runs.find((run) => run.run_id === runId)?.goal_text ?? null;
  } catch {
    return null;
  }
}

export function RunCockpitPage() {
  const { runId } = useParams<{ runId: string }>();
  const navigate = useNavigate();
  const { data: runData, error, loading, refetch } = useRunStatus(runId);
  const { events, connected, usingFallback } = useRunStream(runId);
  const playback = useGuidedPlayback(events, {
    minimumDwellMs: 1_800,
    resetKey: runId,
  });
  const [selectedStageId, setSelectedStageId] = useState<string | null>(null);

  const status = runData?.status ?? null;
  const badge = status ? STATUS_BADGE[status] : null;
  const streamUnavailable = usingFallback && events.length === 0;
  const presentationCaughtUp = playback.isCaughtUp || streamUnavailable;
  const latestVisibleEvent = playback.visibleEvents.at(-1);
  const liveGuide = getActiveGuide(status, runData?.current_node ?? null);
  const guide = !presentationCaughtUp && latestVisibleEvent
    ? getActiveGuide(null, latestVisibleEvent.source)
    : liveGuide;
  const presentationStatus: RunStatus | null = presentationCaughtUp
    ? status
    : guide.id === 'receive'
      ? 'RECEIVED'
      : 'RUNNING';
  const presentationNode = presentationCaughtUp
    ? runData?.current_node ?? null
    : latestVisibleEvent?.source ?? null;
  const activeJourneyStage = normalizeJourneyStage(guide.id);
  const reviewedGuide = selectedStageId
    ? PHASE_GUIDES.find((phase) => phase.id === selectedStageId) ?? null
    : null;
  const briefingGuide = reviewedGuide ?? guide;
  const isReviewingStage = Boolean(
    selectedStageId && selectedStageId !== activeJourneyStage,
  );
  const reviewedEvents = reviewedGuide
    ? playback.visibleEvents.filter((event) => reviewedGuide.matchNodes.includes(event.source))
    : playback.visibleEvents;
  const briefingNode = reviewedGuide?.matchNodes[0] ?? presentationNode;

  const isApproval = presentationCaughtUp && status === 'WAITING_FOR_APPROVAL';
  const isClarification = presentationCaughtUp && status === 'WAITING_FOR_CLARIFICATION';
  const isTerminal = presentationCaughtUp
    && (status === 'COMPLETED' || status === 'FAILED' || status === 'CANCELLED');
  const goalText = readSavedGoal(runId ?? '')
    ?? runData?.structured_goal?.objective
    ?? runData?.structured_goal?.objectives?.[0]
    ?? 'Operational decision goal';

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
      <section
        className="sticky top-[7.05rem] lg:top-16 z-30 border-b border-border-base bg-deep/95 backdrop-blur"
        aria-label="Active goal"
      >
        <div className="max-w-[1440px] mx-auto px-5 sm:px-8 py-3.5 flex flex-col lg:flex-row lg:items-center justify-between gap-3">
          <div className="min-w-0">
            <div className="flex flex-wrap items-center gap-2.5">
              <span className="text-[8px] font-mono font-semibold uppercase tracking-[0.18em] text-ops-amber">
                Today’s goal
              </span>
              <span className="text-[9px] font-mono text-ink-muted">#{runId.slice(0, 12)}</span>
              {badge && (
                <span className={`text-[8px] font-mono px-2 py-1 rounded-full uppercase tracking-[0.1em] font-semibold ${badge.cls}`}>
                  {badge.label}
                </span>
              )}
            </div>
            <h1 className="text-sm sm:text-base font-extrabold tracking-[-0.025em] text-ink-primary mt-1.5 truncate">
              {goalText}
            </h1>
          </div>
          <div className="flex items-center gap-2 shrink-0">
            <span className={`relative w-2 h-2 rounded-full ${connected ? 'bg-ops-cyan' : 'bg-ops-orange'}`}>
              <span className="absolute inset-0 rounded-full bg-current animate-ping opacity-30" />
            </span>
            <span className="text-[9px] font-mono uppercase tracking-[0.15em] text-ink-muted">
              {connected ? 'Live updates' : usingFallback ? 'Safe polling' : 'Connecting'}
            </span>
          </div>
        </div>
      </section>

      <section className="bg-abyss border-b border-border-dim">
        <div className="max-w-[1440px] mx-auto px-5 sm:px-8 pt-5 pb-5">
          <DecisionJourneyRail
            activeId={guide.id}
            selectedId={selectedStageId}
            failed={status === 'FAILED'}
            onSelect={setSelectedStageId}
          />
        </div>
        <PlaybackControls
          playback={playback}
          backendStatus={status}
          presentationLabel={guide.label}
        />
      </section>

      <div className="max-w-[1440px] mx-auto px-5 sm:px-8 py-6 lg:py-8">
        <div className="grid lg:grid-cols-[minmax(0,1fr)_360px] gap-6 items-start">
          <main className="min-w-0 rounded-[1.5rem] border border-border-dim bg-abyss shadow-card overflow-hidden">
            <div className="px-5 sm:px-7 py-5 border-b border-border-dim flex flex-col sm:flex-row sm:items-center gap-3 justify-between">
              <div>
                <div className="text-[9px] font-mono text-ops-amber uppercase tracking-[0.18em] font-semibold">
                  {isReviewingStage ? 'Reviewing' : 'Now'} · step {(PHASE_INDEX[briefingGuide.id] ?? 0) + 1} of 8
                </div>
                <h1 className="text-xl sm:text-2xl font-extrabold tracking-[-0.04em] mt-1">
                  {briefingGuide.label}
                </h1>
              </div>
              {isReviewingStage ? (
                <button
                  type="button"
                  onClick={() => setSelectedStageId(null)}
                  className="text-[10px] font-semibold text-ops-amber hover:underline focus-ring rounded"
                >
                  Back to live route
                </button>
              ) : !isApproval && !isClarification && !isTerminal && (
                <div className="flex items-center gap-2 text-[10px] font-mono text-ink-muted">
                  <span className="w-2 h-2 rounded-full bg-ops-amber animate-pulse" />
                  OptiFlow is working
                </div>
              )}
            </div>

            <div className="p-5 sm:p-7 min-h-[520px]">
              {isReviewingStage ? (
                <EventTimeline
                  events={reviewedEvents}
                  status={null}
                  connected={connected}
                  usingFallback={usingFallback}
                />
              ) : isApproval ? (
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
                <EventTimeline
                  events={playback.visibleEvents}
                  status={presentationStatus}
                  connected={connected}
                  usingFallback={usingFallback}
                />
              )}
            </div>
          </main>

          <aside className="lg:sticky lg:top-24 rounded-[1.5rem] border border-border-dim bg-abyss shadow-card overflow-hidden">
            <MissionGuide
              status={isReviewingStage ? null : presentationStatus}
              currentNode={briefingNode}
            />
          </aside>
        </div>
      </div>
    </div>
  );
}
