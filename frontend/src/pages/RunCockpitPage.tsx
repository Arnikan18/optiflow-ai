import { useParams, useNavigate } from 'react-router-dom';
import { useRunStatus } from '../hooks/useRunStatus';
import { useRunStream } from '../hooks/useRunStream';
import { EventTimeline } from '../components/run/EventTimeline';
import { PlanWorkspace } from '../components/approval/PlanWorkspace';
import { ClarifyPanel } from '../components/clarification/ClarifyPanel';
import { SummaryPanel } from '../components/completion/SummaryPanel';
import { MissionGuide } from '../components/guide/MissionGuide';
import type { RunStatus } from '../types/api';

const STATUS_BADGE: Record<RunStatus, { label: string; cls: string }> = {
  RECEIVED:                  { label: 'Received',             cls: 'text-ink-secondary bg-border-dim' },
  RUNNING:                   { label: 'Running',              cls: 'text-ops-cyan bg-ops-cyan/10' },
  WAITING_FOR_CLARIFICATION: { label: 'Awaiting Clarification', cls: 'text-ops-orange bg-ops-orange/10' },
  WAITING_FOR_APPROVAL:      { label: 'Awaiting Approval',    cls: 'text-ops-amber bg-ops-amber/10' },
  EXECUTING:                 { label: 'Executing',            cls: 'text-ops-orange bg-ops-orange/10' },
  COMPLETED:                 { label: 'Completed',            cls: 'text-ops-emerald bg-ops-emerald/10' },
  FAILED:                    { label: 'Failed',               cls: 'text-ops-rose bg-ops-rose/10' },
};

export function RunCockpitPage() {
  const { runId } = useParams<{ runId: string }>();
  const navigate = useNavigate();
  const { data: runData, error, loading, refetch } = useRunStatus(runId);
  const { events, connected, usingFallback } = useRunStream(runId);

  const status = runData?.status ?? null;
  const badge = status ? STATUS_BADGE[status] : null;

  const isApproval      = status === 'WAITING_FOR_APPROVAL';
  const isClarification = status === 'WAITING_FOR_CLARIFICATION';
  const isTerminal      = status === 'COMPLETED' || status === 'FAILED';

  // ── Loading / error states ─────────────────────────────────────
  if (!runId) {
    return (
      <div className="min-h-screen flex items-center justify-center text-ink-muted text-sm">
        No Run ID in URL.{' '}
        <button onClick={() => navigate('/')} className="text-ops-amber ml-2 hover:underline">
          Return to Control Room
        </button>
      </div>
    );
  }

  if (loading && !runData) {
    return (
      <div className="min-h-screen flex flex-col items-center justify-center gap-4">
        <div className="relative w-10 h-10">
          <div className="absolute inset-0 rounded-full border-2 border-ops-amber/30 animate-spin-slow" />
          <div className="absolute inset-2 rounded-full bg-ops-amber/10" />
        </div>
        <p className="text-sm text-ink-muted font-mono">Loading run {runId}…</p>
      </div>
    );
  }

  if (error && !runData) {
    return (
      <div className="min-h-screen flex flex-col items-center justify-center gap-4 text-center px-6">
        <p className="text-3xl">⚠</p>
        <p className="text-sm text-ops-rose">{error}</p>
        <button onClick={() => navigate('/')} className="text-xs font-mono text-ink-secondary hover:text-ops-amber transition-colors">
          ← Return to Control Room
        </button>
      </div>
    );
  }

  return (
    <div className="flex flex-col h-[calc(100vh-3.5rem)]">
      {/* ── Run header bar ───────────────────────────────────────── */}
      <div className="shrink-0 bg-abyss border-b border-border-dim px-6 py-3 flex items-center gap-4 flex-wrap">
        <div className="flex items-center gap-3 flex-wrap min-w-0">
          <span className="text-xs font-mono text-ink-muted uppercase tracking-widest shrink-0">Run</span>
          <span className="text-xs font-mono text-ink-secondary">{runId}</span>
          {badge && (
            <span className={`text-xs font-mono px-2.5 py-0.5 rounded uppercase tracking-wider font-semibold ${badge.cls}`}>
              {badge.label}
            </span>
          )}
          {runData?.current_node && (
            <span className="text-xs font-mono text-ink-muted hidden sm:block">
              node: {runData.current_node}
            </span>
          )}
        </div>

        {/* Live / fallback indicator */}
        <div className="ml-auto flex items-center gap-2 shrink-0">
          {connected ? (
            <>
              <div className="relative w-2 h-2">
                <div className="absolute inset-0 rounded-full bg-ops-cyan" />
                <div className="absolute inset-0 rounded-full bg-ops-cyan animate-ping opacity-75" />
              </div>
              <span className="text-xs font-mono text-ops-cyan">LIVE</span>
            </>
          ) : (
            <>
              <div className="w-2 h-2 rounded-full bg-ops-orange animate-pulse" />
              <span className="text-xs font-mono text-ops-orange">POLLING</span>
            </>
          )}
        </div>
      </div>

      {/* ── Two-column layout: main + guide ─────────────────────── */}
      <div className="flex flex-1 min-h-0">
        {/* Left / main area */}
        <div className="flex-1 overflow-y-auto p-6 min-w-0">
          {isApproval ? (
            <PlanWorkspace
              runId={runId}
              plans={runData?.candidate_plans ?? []}
              recommendedPlanId={runData?.recommended_plan_id ?? null}
              onApproved={refetch}
            />
          ) : isClarification ? (
            <ClarifyPanel
              runId={runId}
              runData={runData}
              onSubmitted={refetch}
            />
          ) : isTerminal ? (
            <SummaryPanel runData={runData} events={events} />
          ) : (
            <EventTimeline
              events={events}
              status={status}
              connected={connected}
              usingFallback={usingFallback}
            />
          )}
        </div>

        {/* Right: Mission Guide sidebar */}
        <div className="w-80 shrink-0 overflow-y-auto hidden lg:block">
          <MissionGuide
            status={status}
            currentNode={runData?.current_node ?? null}
          />
        </div>
      </div>
    </div>
  );
}
