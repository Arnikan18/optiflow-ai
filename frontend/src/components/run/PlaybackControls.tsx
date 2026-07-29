import type { GuidedPlayback } from '../../hooks/useGuidedPlayback';
import type { RunStatus } from '../../types/api';

interface PlaybackControlsProps {
  playback: GuidedPlayback;
  backendStatus: RunStatus | null;
  presentationLabel: string;
}

function readableStatus(status: RunStatus | null): string {
  if (!status) return 'Connecting';
  const labels: Partial<Record<RunStatus, string>> = {
    RECEIVED: 'Goal received',
    RUNNING: 'Processing',
    WAITING_FOR_CLARIFICATION: 'Clarification ready',
    WAITING_FOR_APPROVAL: 'Approval ready',
    EXECUTING: 'Executing approved plan',
    REPLANNING: 'Replanning',
    EXECUTED: 'Execution complete',
    FAILED_SAGA: 'Execution recovery required',
    COMPLETED: 'Run completed',
    FAILED: 'Run stopped',
    CANCELLED: 'Run cancelled',
  };
  return labels[status] ?? status.replace(/_/g, ' ');
}

export function PlaybackControls({
  playback,
  backendStatus,
  presentationLabel,
}: PlaybackControlsProps) {
  const progress = playback.totalCount > 0
    ? Math.round((playback.revealedCount / playback.totalCount) * 100)
    : 0;

  return (
    <section
      className="border-t border-border-dim bg-deep/70"
      aria-label="Guided playback controls"
    >
      <div className="max-w-[1440px] mx-auto px-5 sm:px-8 py-3.5">
        <div className="grid lg:grid-cols-[minmax(0,1fr)_auto] items-center gap-4">
          <div className="min-w-0">
            <div className="flex flex-wrap items-center gap-x-4 gap-y-2">
              <div className="flex items-center gap-2">
                <span className={`w-2 h-2 rounded-full ${
                  playback.isPaused
                    ? 'bg-ops-orange'
                    : playback.isCaughtUp
                      ? 'bg-ops-emerald'
                      : 'bg-ops-amber animate-pulse'
                }`} />
                <span className="text-[9px] font-mono font-semibold uppercase tracking-[0.16em] text-ink-primary">
                  {playback.isPaused
                    ? 'Guide paused'
                    : playback.isCaughtUp
                      ? 'Guide is live'
                      : 'Guided replay'}
                </span>
              </div>
              <span className="text-[10px] text-ink-muted">
                Showing <strong className="text-ink-secondary">{presentationLabel}</strong>
              </span>
              <span className="text-[10px] text-ink-muted">
                Backend now: <strong className="text-ink-secondary">{readableStatus(backendStatus)}</strong>
              </span>
              {playback.bufferedCount > 0 && (
                <span className="rounded-full bg-ops-amber/10 text-ops-amber px-2 py-1 text-[9px] font-mono font-semibold">
                  {playback.bufferedCount} ready to review
                </span>
              )}
            </div>

            <div className="flex items-center gap-3 mt-2.5">
              <div className="h-1.5 flex-1 max-w-xl rounded-full bg-surface overflow-hidden">
                <div
                  className="h-full rounded-full bg-ops-amber transition-[width] duration-500"
                  style={{ width: `${progress}%` }}
                />
              </div>
              <span className="text-[9px] font-mono text-ink-muted shrink-0">
                {playback.revealedCount}/{playback.totalCount} updates
              </span>
              <span className="hidden xl:inline text-[9px] font-mono text-ink-ghost">
                {playback.prefersReducedMotion
                  ? 'Reduced motion · short dwell'
                  : `${(playback.effectiveDwellMs / 1000).toFixed(1)}s minimum dwell`}
              </span>
            </div>
          </div>

          <div className="flex flex-wrap items-center gap-2">
            <button
              type="button"
              onClick={playback.togglePaused}
              disabled={playback.totalCount === 0 || playback.isCaughtUp}
              className="rounded-lg border border-border-base bg-abyss px-3 py-2 text-[10px] font-semibold text-ink-secondary hover:text-ink-primary disabled:opacity-35 focus-ring"
            >
              {playback.isPaused ? 'Resume walkthrough' : 'Pause walkthrough'}
            </button>
            <button
              type="button"
              onClick={playback.revealNext}
              disabled={playback.bufferedCount === 0}
              className="rounded-lg border border-border-base bg-abyss px-3 py-2 text-[10px] font-semibold text-ink-secondary hover:text-ops-cyan disabled:opacity-35 focus-ring"
            >
              Show next card
            </button>
            <button
              type="button"
              onClick={playback.revealLatest}
              disabled={playback.bufferedCount === 0}
              className="rounded-lg bg-ink-primary text-white px-3 py-2 text-[10px] font-semibold hover:bg-ops-amber disabled:opacity-35 focus-ring"
            >
              Show latest
            </button>
          </div>
        </div>

        <p className="text-[9px] leading-relaxed text-ink-ghost mt-2">
          Sequence and results come from the backend. Presentation dwell is added for readability.
          General event timestamps are not supplied by the current API; solver timing is shown where reported.
        </p>
      </div>
    </section>
  );
}
