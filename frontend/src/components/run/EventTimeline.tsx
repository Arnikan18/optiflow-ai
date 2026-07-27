import { useEffect, useRef } from 'react';
import type { RunEvent, RunStatus } from '../../types/api';
import { NODE_LABELS } from '../../data/guideContent';

interface EventTimelineProps {
  events: RunEvent[];
  status: RunStatus | null;
  connected: boolean;
  usingFallback: boolean;
}

// Map event_type → accent colour token
const EVENT_COLORS: Record<string, { badge: string; dot: string; border: string }> = {
  RUN_STARTED:               { badge: 'text-ops-cyan bg-ops-cyan/10',    dot: 'bg-ops-cyan',    border: 'border-ops-cyan/20' },
  GOAL_INTERPRETED:          { badge: 'text-ops-violet bg-ops-violet/10', dot: 'bg-ops-violet',  border: 'border-ops-violet/20' },
  GOAL_VALIDATED:            { badge: 'text-ops-emerald bg-ops-emerald/10',dot: 'bg-ops-emerald',border: 'border-ops-emerald/20' },
  WAITING_FOR_CLARIFICATION: { badge: 'text-ops-orange bg-ops-orange/10', dot: 'bg-ops-orange',  border: 'border-ops-orange/20' },
  EVIDENCE_PLANNED:          { badge: 'text-ops-cyan bg-ops-cyan/10',    dot: 'bg-ops-cyan',    border: 'border-ops-cyan/20' },
  TOOLS_SELECTED:            { badge: 'text-ops-cyan bg-ops-cyan/10',    dot: 'bg-ops-cyan',    border: 'border-ops-cyan/20' },
  TOOLS_EXECUTED:            { badge: 'text-ops-cyan bg-ops-cyan/10',    dot: 'bg-ops-cyan',    border: 'border-ops-cyan/20' },
  STATE_BUILT:               { badge: 'text-ops-violet bg-ops-violet/10', dot: 'bg-ops-violet',  border: 'border-ops-violet/20' },
  QUALITY_EVALUATED:         { badge: 'text-ops-amber bg-ops-amber/10',  dot: 'bg-ops-amber',   border: 'border-ops-amber/20' },
  PLANS_GENERATED:           { badge: 'text-ops-amber bg-ops-amber/10',  dot: 'bg-ops-amber',   border: 'border-ops-amber/20' },
  WAITING_FOR_APPROVAL:      { badge: 'text-ops-amber bg-ops-amber/10',  dot: 'bg-ops-amber',   border: 'border-ops-amber/20' },
  PLAN_APPROVED:             { badge: 'text-ops-emerald bg-ops-emerald/10',dot: 'bg-ops-emerald',border: 'border-ops-emerald/20' },
  SAGA_EXECUTING:            { badge: 'text-ops-orange bg-ops-orange/10', dot: 'bg-ops-orange',  border: 'border-ops-orange/20' },
  RUN_COMPLETED:             { badge: 'text-ops-emerald bg-ops-emerald/10',dot: 'bg-ops-emerald',border: 'border-ops-emerald/20' },
  RUN_FAILED:                { badge: 'text-ops-rose bg-ops-rose/10',    dot: 'bg-ops-rose',    border: 'border-ops-rose/20' },
};

const DEFAULT_COLOR = { badge: 'text-ink-secondary bg-border-dim', dot: 'bg-ink-muted', border: 'border-border-dim' };

function EventCard({ event, index }: { event: RunEvent; index: number }) {
  const col = EVENT_COLORS[event.event_type] ?? DEFAULT_COLOR;
  const time = event.received_at
    ? new Date(event.received_at).toLocaleTimeString()
    : '';

  return (
    <div
      className={`animate-scan-in relative flex gap-4`}
      style={{ animationDelay: `${Math.min(index * 40, 400)}ms`, opacity: 0 }}
    >
      {/* Left: connector dot + line */}
      <div className="flex flex-col items-center pt-1 shrink-0 w-5">
        <div className={`w-2 h-2 rounded-full shrink-0 ${col.dot}`} />
        <div className="w-px flex-1 bg-border-dim mt-1" />
      </div>

      {/* Right: card */}
      <div className={`flex-1 mb-4 bg-deep border ${col.border} rounded-lg p-4 space-y-2`}>
        <div className="flex items-start justify-between gap-3">
          <span className={`text-xs font-mono font-semibold px-2 py-0.5 rounded uppercase tracking-wider ${col.badge}`}>
            {event.event_type.replace(/_/g, ' ')}
          </span>
          <span className="text-xs font-mono text-ink-muted shrink-0">{time}</span>
        </div>

        {event.summary && (
          <p className="text-sm text-ink-secondary leading-relaxed">{event.summary}</p>
        )}

        <div className="flex items-center gap-3 text-xs font-mono text-ink-muted">
          <span>
            source: <span className="text-ink-secondary">{NODE_LABELS[event.source] ?? event.source}</span>
          </span>
          <span>seq #{event.sequence_number}</span>
        </div>
      </div>
    </div>
  );
}

function StatusBanner({ status }: { status: RunStatus | null }) {
  if (!status || status === 'RUNNING' || status === 'RECEIVED') return null;

  const configs: Record<string, { label: string; cls: string }> = {
    WAITING_FOR_CLARIFICATION: { label: '⚠ Paused — Answer the clarification question to continue', cls: 'border-ops-orange/40 bg-ops-orange/8 text-ops-orange' },
    WAITING_FOR_APPROVAL:      { label: '⚡ Ready for Review — Compare the 4 candidate plans and approve one', cls: 'border-ops-amber/40 bg-ops-amber/8 text-ops-amber' },
    EXECUTING:                 { label: '🔄 Executing — SAGA transactions in progress, do not close this window', cls: 'border-ops-cyan/40 bg-ops-cyan/8 text-ops-cyan' },
    COMPLETED:                 { label: '✅ Mission Complete — All changes have been committed successfully', cls: 'border-ops-emerald/40 bg-ops-emerald/8 text-ops-emerald' },
    FAILED:                    { label: '✗ Execution Failed — Review the error details and retry', cls: 'border-ops-rose/40 bg-ops-rose/8 text-ops-rose' },
  };

  const cfg = configs[status];
  if (!cfg) return null;

  return (
    <div className={`border rounded-lg px-4 py-3 mb-4 text-sm font-semibold animate-fade-up ${cfg.cls}`}>
      {cfg.label}
    </div>
  );
}

export function EventTimeline({ events, status, connected, usingFallback }: EventTimelineProps) {
  const bottomRef = useRef<HTMLDivElement>(null);

  // Auto-scroll to latest event
  useEffect(() => {
    bottomRef.current?.scrollIntoView({ behavior: 'smooth' });
  }, [events.length]);

  return (
    <div className="flex flex-col h-full">
      {/* Stream indicator */}
      <div className="flex items-center justify-between mb-4 shrink-0">
        <h2 className="text-xs font-mono text-ink-secondary uppercase tracking-widest">
          Agent Event Stream
        </h2>
        <div className="flex items-center gap-2 text-xs font-mono">
          {connected ? (
            <>
              <div className="relative w-2 h-2">
                <div className="absolute inset-0 rounded-full bg-ops-cyan" />
                <div className="absolute inset-0 rounded-full bg-ops-cyan animate-ping opacity-75" />
              </div>
              <span className="text-ops-cyan">SSE LIVE</span>
            </>
          ) : usingFallback ? (
            <>
              <div className="w-2 h-2 rounded-full bg-ops-orange animate-pulse" />
              <span className="text-ops-orange">POLLING</span>
            </>
          ) : (
            <>
              <div className="w-2 h-2 rounded-full bg-ink-muted" />
              <span className="text-ink-muted">CONNECTING…</span>
            </>
          )}
          <span className="text-ink-muted">{events.length} events</span>
        </div>
      </div>

      <StatusBanner status={status} />

      {/* Events */}
      <div className="flex-1 overflow-y-auto pr-1">
        {events.length === 0 ? (
          <div className="flex flex-col items-center justify-center py-16 text-center space-y-3">
            <div className="relative w-8 h-8">
              <div className="absolute inset-0 rounded-full border-2 border-ops-cyan/30 animate-spin-slow" />
              <div className="absolute inset-1 rounded-full bg-ops-cyan/10" />
            </div>
            <p className="text-sm text-ink-muted">Waiting for agent signals…</p>
            <p className="text-xs text-ink-ghost font-mono">Stream will populate as the agent executes each node</p>
          </div>
        ) : (
          events.map((ev, i) => <EventCard key={ev.event_id} event={ev} index={i} />)
        )}
        <div ref={bottomRef} />
      </div>
    </div>
  );
}
