import { useEffect, useRef } from 'react';
import type { RunEvent, RunStatus } from '../../types/api';
import { NODE_LABELS } from '../../data/guideContent';

interface EventTimelineProps {
  events: RunEvent[];
  status: RunStatus | null;
  connected: boolean;
  usingFallback: boolean;
}

interface EventMeta {
  label: string;
  engine: string;
  explanation: string;
  checks: string[];
  color: string;
  bg: string;
}

const EVENT_META: Record<string, EventMeta> = {
  RUN_STARTED: {
    label: 'Route opened',
    engine: 'OptiFlow Core',
    explanation: 'A traceable workspace was created for this decision.',
    checks: ['Run identity', 'Audit context'],
    color: 'text-ops-cyan',
    bg: 'bg-ops-cyan',
  },
  GOAL_INTERPRETED: {
    label: 'Goal framed',
    engine: 'Intent engine',
    explanation: 'Your words were separated into priorities, limits, and timing.',
    checks: ['Objective', 'Constraints', 'Horizon'],
    color: 'text-ops-violet',
    bg: 'bg-ops-violet',
  },
  GOAL_VALIDATED: {
    label: 'Policy guard passed',
    engine: 'Policy engine',
    explanation: 'The goal is specific enough and safe to use for planning.',
    checks: ['Policy fit', 'Ambiguity', 'Missing rules'],
    color: 'text-ops-emerald',
    bg: 'bg-ops-emerald',
  },
  WAITING_FOR_CLARIFICATION: {
    label: 'Human answer needed',
    engine: 'Policy engine',
    explanation: 'A choice is too important for the system to assume.',
    checks: ['Conflicting priority', 'Decision owner'],
    color: 'text-ops-orange',
    bg: 'bg-ops-orange',
  },
  EVIDENCE_PLANNED: {
    label: 'Evidence mapped',
    engine: 'Evidence engine',
    explanation: 'OptiFlow identified the facts required to make this decision.',
    checks: ['Needed sources', 'Required fields'],
    color: 'text-ops-cyan',
    bg: 'bg-ops-cyan',
  },
  TOOLS_SELECTED: {
    label: 'Sources connected',
    engine: 'Evidence engine',
    explanation: 'The relevant enterprise systems were selected for live checks.',
    checks: ['CRM', 'Incidents', 'Workforce', 'Comms'],
    color: 'text-ops-cyan',
    bg: 'bg-ops-cyan',
  },
  TOOLS_EXECUTED: {
    label: 'Live data collected',
    engine: 'Enterprise services',
    explanation: 'Current customer, incident, and team facts were retrieved.',
    checks: ['ARR and tier', 'SLA deadline', 'Availability', 'Workload'],
    color: 'text-ops-cyan',
    bg: 'bg-ops-cyan',
  },
  STATE_BUILT: {
    label: 'Portfolio picture built',
    engine: 'State engine',
    explanation: 'Evidence from separate systems was joined into one decision view.',
    checks: ['Cross-source match', 'Freshness', 'Conflicts'],
    color: 'text-ops-violet',
    bg: 'bg-ops-violet',
  },
  QUALITY_EVALUATED: {
    label: 'Evidence quality checked',
    engine: 'Quality engine',
    explanation: 'OptiFlow tested whether the data is complete and trustworthy.',
    checks: ['Completeness', 'Freshness', 'Confidence'],
    color: 'text-ops-amber',
    bg: 'bg-ops-amber',
  },
  PLANS_GENERATED: {
    label: 'Trade-offs compared',
    engine: 'Optimisation engine',
    explanation: 'Multiple valid assignments were scored from different priorities.',
    checks: ['SLA coverage', 'ARR protected', 'Fairness', 'Feasibility'],
    color: 'text-ops-amber',
    bg: 'bg-ops-amber',
  },
  WAITING_FOR_APPROVAL: {
    label: 'Decision ready',
    engine: 'Human approval gate',
    explanation: 'Planning is complete. Nothing changes until you choose.',
    checks: ['Recommendation', 'Alternatives', 'Explicit consent'],
    color: 'text-ops-amber',
    bg: 'bg-ops-amber',
  },
  PLAN_APPROVED: {
    label: 'Plan authorised',
    engine: 'Human approval gate',
    explanation: 'Your selected trade-off was recorded in the audit trail.',
    checks: ['Approver', 'Chosen plan', 'Timestamp'],
    color: 'text-ops-emerald',
    bg: 'bg-ops-emerald',
  },
  SAGA_EXECUTING: {
    label: 'Changes applying safely',
    engine: 'Execution engine',
    explanation: 'Each change is written and confirmed before the next begins.',
    checks: ['Reserve', 'Assign', 'Notify', 'Verify'],
    color: 'text-ops-orange',
    bg: 'bg-ops-orange',
  },
  RUN_COMPLETED: {
    label: 'Every change verified',
    engine: 'OptiFlow Core',
    explanation: 'All writes succeeded and execution receipts were stored.',
    checks: ['Receipts', 'Final state', 'Audit close'],
    color: 'text-ops-emerald',
    bg: 'bg-ops-emerald',
  },
  RUN_FAILED: {
    label: 'Route safely stopped',
    engine: 'Safety controller',
    explanation: 'Partial actions were reversed and the failure was recorded.',
    checks: ['Rollback', 'System consistency', 'Failure context'],
    color: 'text-ops-rose',
    bg: 'bg-ops-rose',
  },
};

const DEFAULT_META: EventMeta = {
  label: 'Agent update',
  engine: 'OptiFlow',
  explanation: 'The decision route moved forward.',
  checks: ['Event recorded'],
  color: 'text-ink-secondary',
  bg: 'bg-ink-muted',
};

function EventCard({ event, index, isLatest }: { event: RunEvent; index: number; isLatest: boolean }) {
  const meta = EVENT_META[event.event_type] ?? DEFAULT_META;
  const time = event.received_at ? new Date(event.received_at).toLocaleTimeString([], { hour: '2-digit', minute: '2-digit', second: '2-digit' }) : 'recorded';

  return (
    <article
      className="animate-fade-up relative grid grid-cols-[38px_minmax(0,1fr)] gap-3 sm:gap-5"
      style={{ animationDelay: `${Math.min(index * 45, 360)}ms`, opacity: 0 }}
    >
      <div className="relative flex justify-center">
        <div className={`relative z-10 mt-1 w-7 h-7 rounded-full border-4 border-abyss ${meta.bg} ${isLatest ? 'route-pulse' : ''} flex items-center justify-center`}>
          {isLatest && <span className="w-1.5 h-1.5 rounded-full bg-white" />}
        </div>
        <div className="absolute top-7 bottom-0 w-px bg-border-dim" />
      </div>

      <div className={`mb-4 rounded-2xl border p-4 sm:p-5 transition-all ${
        isLatest ? 'border-ops-amber/40 bg-ops-amber/[0.035] shadow-card' : 'border-border-dim bg-deep/60'
      }`}>
        <div className="flex items-start justify-between gap-4">
          <div>
            <div className="flex flex-wrap items-center gap-2">
              <h3 className="text-sm font-bold text-ink-primary">{meta.label}</h3>
              {isLatest && (
                <span className="text-[8px] font-mono uppercase tracking-[0.14em] rounded-full bg-ops-amber text-white px-2 py-1">current</span>
              )}
            </div>
            <p className={`text-[9px] font-mono uppercase tracking-[0.15em] mt-1.5 ${meta.color}`}>{meta.engine}</p>
          </div>
          <time className="text-[9px] font-mono text-ink-muted whitespace-nowrap">{time}</time>
        </div>

        <p className="text-xs sm:text-sm text-ink-secondary leading-relaxed mt-4">
          {event.summary || meta.explanation}
        </p>

        <div className="mt-4 pt-4 border-t border-border-dim">
          <p className="text-[8px] font-mono uppercase tracking-[0.16em] text-ink-muted mb-2.5">What was checked</p>
          <div className="flex flex-wrap gap-2">
            {meta.checks.map((check) => (
              <span key={check} className="inline-flex items-center gap-1.5 rounded-full border border-border-dim bg-abyss px-2.5 py-1 text-[10px] text-ink-secondary">
                <span className={`w-1 h-1 rounded-full ${meta.bg}`} />
                {check}
              </span>
            ))}
          </div>
        </div>

        <div className="mt-3 flex flex-wrap gap-x-4 gap-y-1 text-[9px] font-mono text-ink-muted">
          <span>{NODE_LABELS[event.source] ?? event.source}</span>
          <span>event {String(event.sequence_number).padStart(2, '0')}</span>
        </div>
      </div>
    </article>
  );
}

function StatusBanner({ status }: { status: RunStatus | null }) {
  const configs: Partial<Record<RunStatus, { eyebrow: string; label: string; cls: string }>> = {
    WAITING_FOR_CLARIFICATION: { eyebrow: 'Your move', label: 'Answer the question below so the route can continue without assumptions.', cls: 'border-ops-orange/30 bg-ops-orange/5 text-ops-orange' },
    WAITING_FOR_APPROVAL: { eyebrow: 'Your move', label: 'Compare the candidate plans and authorise the trade-off you accept.', cls: 'border-ops-amber/30 bg-ops-amber/5 text-ops-amber' },
    EXECUTING: { eyebrow: 'In progress', label: 'Changes are being applied one at a time and verified after every write.', cls: 'border-ops-cyan/30 bg-ops-cyan/5 text-ops-cyan' },
    COMPLETED: { eyebrow: 'Finished', label: 'All changes were confirmed and the audit trail is complete.', cls: 'border-ops-emerald/30 bg-ops-emerald/5 text-ops-emerald' },
    FAILED: { eyebrow: 'Safely stopped', label: 'Partial changes were rolled back. Review the failure before retrying.', cls: 'border-ops-rose/30 bg-ops-rose/5 text-ops-rose' },
  };

  const config = status ? configs[status] : null;
  if (!config) return null;

  return (
    <div className={`border rounded-xl px-4 py-3.5 mb-5 ${config.cls}`}>
      <p className="text-[8px] font-mono font-semibold uppercase tracking-[0.16em] opacity-70">{config.eyebrow}</p>
      <p className="text-xs font-semibold mt-1">{config.label}</p>
    </div>
  );
}

export function EventTimeline({ events, status, connected, usingFallback }: EventTimelineProps) {
  const bottomRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    bottomRef.current?.scrollIntoView({ behavior: 'smooth', block: 'nearest' });
  }, [events.length]);

  return (
    <div>
      <div className="flex flex-wrap items-center justify-between gap-3 mb-5">
        <div>
          <h2 className="text-sm font-bold text-ink-primary">Decision log</h2>
          <p className="text-[10px] text-ink-muted mt-1">A plain-language record of each check and hand-off.</p>
        </div>
        <div className="flex items-center gap-2 text-[9px] font-mono uppercase tracking-[0.12em] text-ink-muted">
          <span className={`w-1.5 h-1.5 rounded-full ${connected ? 'bg-ops-cyan' : usingFallback ? 'bg-ops-orange' : 'bg-ink-muted'}`} />
          {connected ? 'streaming' : usingFallback ? 'polling' : 'connecting'}
          <span className="text-border-base">·</span>
          {events.length} updates
        </div>
      </div>

      <StatusBanner status={status} />

      {events.length === 0 ? (
        <div className="rounded-2xl border border-dashed border-border-base bg-deep/50 py-14 px-6 text-center">
          <div className="mx-auto w-10 h-10 rounded-full border border-border-base bg-abyss flex items-center justify-center">
            <span className="w-3 h-3 rounded-full border-2 border-ops-cyan/30 border-t-ops-cyan animate-spin" />
          </div>
          <p className="text-sm font-semibold text-ink-primary mt-4">Preparing the first check</p>
          <p className="text-xs text-ink-muted mt-1.5">Updates will appear here in the order they happen.</p>
        </div>
      ) : (
        <div>
          {events.map((event, index) => (
            <EventCard key={event.event_id} event={event} index={index} isLatest={index === events.length - 1} />
          ))}
          <div ref={bottomRef} />
        </div>
      )}
    </div>
  );
}
