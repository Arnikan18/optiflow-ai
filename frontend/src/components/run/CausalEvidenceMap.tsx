import { useEffect, useMemo, useState } from 'react';
import type { RunEvent } from '../../types/api';

interface CausalEvidenceMapProps {
  phaseId: string;
  events: RunEvent[];
}

type DetailView = 'pulled' | 'checked' | 'decided' | 'alternatives';

interface PhaseLogic {
  checks: string[];
  effect: string;
  alternative: string;
}

const PHASE_LOGIC: Record<string, PhaseLogic> = {
  receive: {
    checks: ['Goal text is valid', 'Run identity is unique'],
    effect: 'An auditable route can begin.',
    alternative: 'Invalid or missing goal text would stop before interpretation.',
  },
  interpret: {
    checks: ['Priority is identifiable', 'Limits are separated', 'Time horizon is present'],
    effect: 'A structured goal is ready for policy checks.',
    alternative: 'Unresolved ambiguity sends the route to a human clarification branch.',
  },
  validate: {
    checks: ['Policy fit', 'Critical ambiguity', 'Decision owner is known'],
    effect: 'The route continues or pauses without making an unsafe assumption.',
    alternative: 'A failed guard can request clarification or close the route safely.',
  },
  clarify: {
    checks: ['Owner answered', 'Conflict is resolved', 'Answer is recorded'],
    effect: 'Evidence collection can resume.',
    alternative: 'No answer leaves the route paused; a conflicting answer returns to validation.',
  },
  evidence: {
    checks: ['Source availability', 'Data freshness', 'Cross-source conflicts'],
    effect: 'A joined operational state becomes available for planning.',
    alternative: 'Missing or stale sources produce partial evidence or a safe stop.',
  },
  optimize: {
    checks: ['Hard constraints', 'Plan feasibility', 'Profile tradeoffs'],
    effect: 'Candidate plans can enter the human approval gate.',
    alternative: 'SLA-first, revenue-first, fairness-first, and balanced profiles change who is helped and who waits.',
  },
  approval: {
    checks: ['Recommendation is visible', 'Tradeoff is understood', 'Consent is explicit'],
    effect: 'Only the selected plan becomes eligible for execution.',
    alternative: 'Modify returns to planning; reject closes safely; no answer leaves the route waiting.',
  },
  executing: {
    checks: ['Write is confirmed', 'Next action is safe', 'Compensation is available'],
    effect: 'The route advances one verified change at a time.',
    alternative: 'A rejected assignment can replan; a failed write can compensate and stop.',
  },
  complete: {
    checks: ['Receipts are present', 'Final state is verified', 'Audit record is closed'],
    effect: 'The outcome can be reviewed and audited.',
    alternative: 'Failed verification keeps the route open for recovery instead of showing success.',
  },
  failed: {
    checks: ['Failure is located', 'Partial work is reversed', 'State is consistent'],
    effect: 'A manager can retry or revise without hidden partial work.',
    alternative: 'Retry follows the recorded recovery point; revision returns to planning.',
  },
};

const ENGINES = [
  {
    id: 'crm',
    label: 'CRM',
    aliases: ['crm', 'customer', 'arr', 'renewal', 'account'],
    tone: 'border-ops-violet/35 bg-ops-violet/10 text-ops-violet',
  },
  {
    id: 'incident',
    label: 'INC',
    aliases: ['incident', 'severity', 'sla', 'assignment_status'],
    tone: 'border-ops-rose/35 bg-ops-rose/10 text-ops-rose',
  },
  {
    id: 'workforce',
    label: 'TEAM',
    aliases: ['workforce', 'specialist', 'skill', 'capacity', 'workload', 'reservation'],
    tone: 'border-ops-cyan/35 bg-ops-cyan/10 text-ops-cyan',
  },
  {
    id: 'communication',
    label: 'COMMS',
    aliases: ['communication', 'notification', 'recipient', 'delivery', 'message'],
    tone: 'border-ops-orange/35 bg-ops-orange/10 text-ops-orange',
  },
];

const VIEW_META: Record<DetailView, {
  number: string;
  label: string;
  prompt: string;
  tone: string;
  icon: 'download' | 'shield' | 'decision' | 'branch';
}> = {
  pulled: {
    number: '01',
    label: 'Pulled',
    prompt: 'What came in?',
    tone: 'text-ops-cyan border-ops-cyan/35 bg-ops-cyan/[0.055]',
    icon: 'download',
  },
  checked: {
    number: '02',
    label: 'Checked',
    prompt: 'What rules ran?',
    tone: 'text-ops-violet border-ops-violet/35 bg-ops-violet/[0.055]',
    icon: 'shield',
  },
  decided: {
    number: '03',
    label: 'Decided',
    prompt: 'What was recorded?',
    tone: 'text-ops-amber border-ops-amber/35 bg-ops-amber/[0.055]',
    icon: 'decision',
  },
  alternatives: {
    number: '04',
    label: 'Alternatives',
    prompt: 'What else could happen?',
    tone: 'text-ops-orange border-ops-orange/35 bg-ops-orange/[0.055]',
    icon: 'branch',
  },
};

function Icon({
  name,
  className = 'w-4 h-4',
}: {
  name: 'download' | 'shield' | 'decision' | 'branch' | 'check';
  className?: string;
}) {
  const paths = {
    download: (
      <>
        <path d="M12 3v11M8 10l4 4 4-4" />
        <path d="M5 18v2h14v-2" />
      </>
    ),
    shield: (
      <>
        <path d="M12 3 5 6v5c0 4.8 2.8 8 7 10 4.2-2 7-5.2 7-10V6l-7-3Z" />
        <path d="m9 12 2 2 4-4" />
      </>
    ),
    decision: (
      <>
        <circle cx="12" cy="12" r="8" />
        <path d="m8.5 12 2.2 2.2 4.8-5" />
      </>
    ),
    branch: (
      <>
        <path d="M6 4v5a3 3 0 0 0 3 3h9" />
        <path d="m15 9 3 3-3 3M6 20v-3a5 5 0 0 1 5-5" />
      </>
    ),
    check: <path d="m5 12 4 4L19 6" />,
  };

  return (
    <svg
      viewBox="0 0 24 24"
      fill="none"
      stroke="currentColor"
      strokeWidth="1.8"
      strokeLinecap="round"
      strokeLinejoin="round"
      className={className}
      aria-hidden="true"
    >
      {paths[name]}
    </svg>
  );
}

function collectPayloadFields(
  value: unknown,
  prefix = '',
  depth = 0,
): string[] {
  if (!value || typeof value !== 'object' || depth > 1) return [];

  return Object.entries(value as Record<string, unknown>).flatMap(([key, child]) => {
    const field = prefix ? `${prefix}.${key}` : key;
    return [field, ...collectPayloadFields(child, field, depth + 1)];
  });
}

function readableEventType(eventType: string): string {
  return eventType
    .toLowerCase()
    .replace(/_/g, ' ')
    .replace(/^\w/, (letter) => letter.toUpperCase());
}

export function CausalEvidenceMap({ phaseId, events }: CausalEvidenceMapProps) {
  const [activeView, setActiveView] = useState<DetailView>('pulled');
  const logic = PHASE_LOGIC[phaseId] ?? PHASE_LOGIC.receive;
  const latestEvent = events.at(-1);
  const payloadFields = useMemo(() => Array.from(
    new Set(events.flatMap((event) => collectPayloadFields(event.payload))),
  ).slice(0, 8), [events]);
  const sourceLabels = Array.from(new Set(events.map((event) => event.source))).slice(0, 4);
  const presentedEvidence = JSON.stringify(
    events.map((event) => ({ source: event.source, payload: event.payload })),
  ).toLowerCase();
  const inputs = payloadFields.length > 0 ? payloadFields : sourceLabels;
  const outcome = latestEvent?.summary
    ?? (latestEvent ? readableEventType(latestEvent.event_type) : 'Waiting for a recorded event');

  useEffect(() => {
    setActiveView('pulled');
  }, [phaseId]);

  const panelContent: Record<DetailView, React.ReactNode> = {
    pulled: (
      <div>
        <div className="flex flex-wrap gap-1.5">
          {ENGINES.map((engine) => {
            const mentioned = engine.aliases.some((alias) => presentedEvidence.includes(alias));
            return (
              <span
                key={engine.id}
                className={`rounded-full border px-2.5 py-1 text-[8px] font-mono font-bold ${
                  mentioned ? engine.tone : 'border-border-dim bg-deep text-ink-ghost'
                }`}
              >
                {engine.label}
                <span className={`inline-block w-1 h-1 rounded-full ml-1.5 ${
                  mentioned ? 'bg-current' : 'bg-ink-ghost'
                }`} />
              </span>
            );
          })}
        </div>
        <div className="flex flex-wrap gap-1.5 mt-4">
          {inputs.length > 0 ? inputs.map((input) => (
            <code key={input} className="rounded-lg border border-border-dim bg-abyss px-2.5 py-1.5 text-[8px] text-ink-secondary">
              {input}
            </code>
          )) : (
            <p className="text-[10px] text-ink-muted">No fields have been presented for this node yet.</p>
          )}
        </div>
      </div>
    ),
    checked: (
      <ul className="grid sm:grid-cols-3 gap-2">
        {logic.checks.map((check) => (
          <li key={check} className="rounded-xl border border-border-dim bg-abyss p-3 flex items-start gap-2">
            <span className="w-5 h-5 shrink-0 rounded-full bg-ops-violet/10 text-ops-violet flex items-center justify-center">
              <Icon name="check" className="w-3 h-3" />
            </span>
            <span className="text-[10px] font-semibold leading-relaxed text-ink-secondary">{check}</span>
          </li>
        ))}
      </ul>
    ),
    decided: (
      <div className="grid sm:grid-cols-[1fr_auto] gap-4 items-center">
        <div className="rounded-xl border border-ops-amber/30 bg-ops-amber/5 p-4">
          <p className="text-[8px] font-mono uppercase tracking-[0.13em] text-ops-amber">Recorded result</p>
          <p className="text-xs font-bold leading-relaxed text-ink-primary mt-2">{outcome}</p>
        </div>
        <div className="max-w-xs">
          <p className="text-[8px] font-mono uppercase tracking-[0.13em] text-ink-muted">Effect</p>
          <p className="text-[10px] leading-relaxed text-ink-secondary mt-2">{logic.effect}</p>
        </div>
      </div>
    ),
    alternatives: (
      <div className="rounded-xl border border-ops-orange/30 bg-ops-orange/5 p-4 flex items-start gap-3">
        <span className="w-8 h-8 shrink-0 rounded-full bg-ops-orange/10 text-ops-orange flex items-center justify-center">
          <Icon name="branch" />
        </span>
        <div>
          <p className="text-[8px] font-mono uppercase tracking-[0.13em] text-ops-orange">Other path</p>
          <p className="text-[10px] leading-relaxed text-ink-secondary mt-2">{logic.alternative}</p>
        </div>
      </div>
    ),
  };

  return (
    <section className="rounded-2xl border border-border-dim bg-deep/50 p-4 sm:p-5 mb-6" aria-labelledby="node-questions-title">
      <div className="flex flex-wrap items-start justify-between gap-3">
        <div>
          <p className="text-[8px] font-mono font-semibold uppercase tracking-[0.17em] text-ops-cyan">
            Selected node
          </p>
          <h2 id="node-questions-title" className="text-sm font-extrabold tracking-[-0.025em] text-ink-primary mt-1">
            Four answers. Full evidence on demand.
          </h2>
        </div>
        <span className="rounded-full border border-border-dim bg-abyss px-2.5 py-1 text-[8px] font-mono text-ink-muted">
          {events.length} event{events.length === 1 ? '' : 's'}
        </span>
      </div>

      <div className="grid grid-cols-2 lg:grid-cols-4 gap-2 mt-4" role="tablist" aria-label="Node explanation">
        {(Object.keys(VIEW_META) as DetailView[]).map((view) => {
          const meta = VIEW_META[view];
          const active = activeView === view;
          return (
            <button
              key={view}
              type="button"
              role="tab"
              aria-selected={active}
              onClick={() => setActiveView(view)}
              className={`rounded-xl border p-3 text-left transition-all focus-ring ${
                active ? `${meta.tone} shadow-card -translate-y-0.5` : 'border-border-dim bg-abyss text-ink-muted hover:border-border-base'
              }`}
            >
              <div className="flex items-center justify-between gap-2">
                <Icon name={meta.icon} />
                <span className="text-[8px] font-mono opacity-60">{meta.number}</span>
              </div>
              <p className="text-[10px] font-extrabold mt-2">{meta.label}</p>
              <p className="text-[8px] mt-0.5 opacity-70">{meta.prompt}</p>
            </button>
          );
        })}
      </div>

      <div
        role="tabpanel"
        className="rounded-xl border border-border-dim bg-deep/70 p-4 mt-2 min-h-[104px] animate-fade-in"
        key={activeView}
      >
        {panelContent[activeView]}
      </div>

      <details className="group mt-3">
        <summary className="cursor-pointer list-none rounded-xl border border-border-dim bg-abyss px-4 py-3 flex items-center justify-between gap-3 text-[9px] font-semibold text-ink-secondary hover:border-border-base focus-ring">
          <span>View complete presented evidence</span>
          <span className="text-ops-cyan group-open:rotate-45 transition-transform">+</span>
        </summary>
        <div className="rounded-xl border border-border-dim bg-abyss p-4 mt-2 space-y-3">
          {events.length > 0 ? events.map((event, index) => (
            <article key={`${event.event_type}-${index}`} className="border-b border-border-dim pb-3 last:border-0 last:pb-0">
              <div className="flex flex-wrap items-center justify-between gap-2">
                <p className="text-[9px] font-mono font-bold text-ink-secondary">
                  {readableEventType(event.event_type)}
                </p>
                <span className="text-[8px] font-mono text-ink-muted">{event.source}</span>
              </div>
              {event.summary && (
                <p className="text-[9px] leading-relaxed text-ink-muted mt-1.5">{event.summary}</p>
              )}
              <pre className="max-h-52 overflow-auto rounded-lg bg-deep p-3 mt-2 text-[8px] leading-relaxed text-ink-muted">
                {JSON.stringify(event.payload, null, 2)}
              </pre>
            </article>
          )) : (
            <p className="text-[10px] text-ink-muted">No event payload is available for this node yet.</p>
          )}
        </div>
      </details>
    </section>
  );
}
