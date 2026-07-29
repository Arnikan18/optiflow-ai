import type { RunEvent } from '../../types/api';

interface CausalEvidenceMapProps {
  phaseId: string;
  events: RunEvent[];
}

const PHASE_LOGIC: Record<string, { checks: string[]; effect: string }> = {
  receive: {
    checks: ['Valid goal text', 'Unique run identity'],
    effect: 'The interpretation step can begin with an auditable reference.',
  },
  interpret: {
    checks: ['Priority found', 'Limits separated', 'Time horizon found'],
    effect: 'A structured goal is available for policy validation.',
  },
  validate: {
    checks: ['Policy fit', 'Critical ambiguity', 'Missing decision owner'],
    effect: 'The route either continues safely or pauses for clarification.',
  },
  clarify: {
    checks: ['Owner answered', 'Conflict resolved', 'Answer recorded'],
    effect: 'Evidence collection resumes without an unsafe assumption.',
  },
  evidence: {
    checks: ['Source availability', 'Freshness', 'Cross-source conflicts'],
    effect: 'A joined operational state becomes available for planning.',
  },
  optimize: {
    checks: ['Hard constraints', 'Feasibility', 'Profile tradeoffs'],
    effect: 'Candidate plans can be compared at the human approval gate.',
  },
  approval: {
    checks: ['Recommendation understood', 'Tradeoff accepted', 'Explicit consent'],
    effect: 'Only the selected plan becomes eligible for execution.',
  },
  executing: {
    checks: ['Write confirmed', 'Next action safe', 'Compensation available'],
    effect: 'The route advances one verified change at a time.',
  },
  complete: {
    checks: ['Receipts present', 'Final state verified', 'Audit record closed'],
    effect: 'The outcome can be reviewed, repeated, and audited later.',
  },
  failed: {
    checks: ['Failure located', 'Partial work reversed', 'State consistent'],
    effect: 'A manager can retry or revise the route without hidden partial changes.',
  },
};

const ENGINES = [
  {
    id: 'crm',
    label: 'CRM',
    role: 'Customer value',
    detail: 'Tier, ARR, renewal risk, and account priority.',
    aliases: ['crm', 'customer', 'arr', 'renewal', 'account'],
    tone: 'text-ops-violet bg-ops-violet/10 border-ops-violet/40',
  },
  {
    id: 'incident',
    label: 'Incident',
    role: 'Service urgency',
    detail: 'Severity, ownership, status, and SLA deadline.',
    aliases: ['incident', 'severity', 'sla', 'assignment_status'],
    tone: 'text-ops-rose bg-ops-rose/10 border-ops-rose/40',
  },
  {
    id: 'workforce',
    label: 'Workforce',
    role: 'Team capacity',
    detail: 'Skills, availability, workload, and reservations.',
    aliases: ['workforce', 'specialist', 'skill', 'capacity', 'workload', 'reservation'],
    tone: 'text-ops-cyan bg-ops-cyan/10 border-ops-cyan/40',
  },
  {
    id: 'communication',
    label: 'Communication',
    role: 'Confirmed handoff',
    detail: 'Recipients, delivery state, and duplicate protection.',
    aliases: ['communication', 'notification', 'recipient', 'delivery', 'message'],
    tone: 'text-ops-orange bg-ops-orange/10 border-ops-orange/30',
  },
];

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
  const logic = PHASE_LOGIC[phaseId] ?? PHASE_LOGIC.receive;
  const latestEvent = events.at(-1);
  const payloadFields = Array.from(
    new Set(events.flatMap((event) => collectPayloadFields(event.payload))),
  ).slice(0, 6);
  const sourceLabels = Array.from(new Set(events.map((event) => event.source))).slice(0, 4);
  const presentedEvidence = JSON.stringify(
    events.map((event) => ({ source: event.source, payload: event.payload })),
  ).toLowerCase();

  const inputs = payloadFields.length > 0 ? payloadFields : sourceLabels;
  const outcome = latestEvent?.summary
    ?? (latestEvent ? readableEventType(latestEvent.event_type) : 'Waiting for a presented event');

  return (
    <section className="rounded-2xl border border-border-dim bg-deep/50 p-4 sm:p-5 mb-6" aria-labelledby="causal-map-title">
      <div className="flex flex-wrap items-start justify-between gap-3">
        <div>
          <p className="text-[8px] font-mono font-semibold uppercase tracking-[0.17em] text-ops-cyan">
            Why the route moved
          </p>
          <h2 id="causal-map-title" className="text-sm font-extrabold tracking-[-0.025em] text-ink-primary mt-1">
            Presented data → checks → result → effect
          </h2>
        </div>
        <span className="rounded-full border border-border-dim bg-abyss px-2.5 py-1 text-[8px] font-mono text-ink-muted">
          {events.length} event{events.length === 1 ? '' : 's'} in this card
        </span>
      </div>

      <div className="grid lg:grid-cols-[1fr_auto_1fr_auto_1fr_auto_1fr] gap-2 lg:items-stretch mt-4">
        <div className="rounded-xl border border-border-dim bg-abyss p-3.5">
          <p className="text-[8px] font-mono uppercase tracking-[0.14em] text-ink-muted">01 · Presented data</p>
          {inputs.length > 0 ? (
            <div className="flex flex-wrap gap-1.5 mt-3">
              {inputs.map((input) => (
                <code key={input} className="rounded bg-surface px-2 py-1 text-[8px] text-ink-secondary">
                  {input}
                </code>
              ))}
            </div>
          ) : (
            <p className="text-[10px] leading-relaxed text-ink-muted mt-3">No fields presented yet.</p>
          )}
        </div>
        <span className="hidden lg:flex items-center text-ops-cyan" aria-hidden="true">→</span>

        <div className="rounded-xl border border-border-dim bg-abyss p-3.5">
          <p className="text-[8px] font-mono uppercase tracking-[0.14em] text-ink-muted">02 · Route checks</p>
          <ul className="space-y-1.5 mt-3">
            {logic.checks.map((check) => (
              <li key={check} className="flex gap-2 text-[9px] leading-relaxed text-ink-secondary">
                <span className="text-ops-cyan">✓</span>
                {check}
              </li>
            ))}
          </ul>
        </div>
        <span className="hidden lg:flex items-center text-ops-cyan" aria-hidden="true">→</span>

        <div className="rounded-xl border border-ops-amber/30 bg-ops-amber/5 p-3.5">
          <p className="text-[8px] font-mono uppercase tracking-[0.14em] text-ops-amber">03 · Recorded result</p>
          <p className="text-[10px] font-semibold leading-relaxed text-ink-primary mt-3">{outcome}</p>
        </div>
        <span className="hidden lg:flex items-center text-ops-cyan" aria-hidden="true">→</span>

        <div className="rounded-xl border border-ops-emerald/30 bg-ops-emerald/5 p-3.5">
          <p className="text-[8px] font-mono uppercase tracking-[0.14em] text-ops-emerald">04 · Downstream effect</p>
          <p className="text-[10px] leading-relaxed text-ink-secondary mt-3">{logic.effect}</p>
        </div>
      </div>

      <div className="mt-4 pt-4 border-t border-border-dim">
        <p className="text-[8px] font-mono uppercase tracking-[0.15em] text-ink-muted mb-2.5">
          Enterprise engine responsibilities
        </p>
        <div className="grid sm:grid-cols-2 xl:grid-cols-4 gap-2">
          {ENGINES.map((engine) => {
            const mentioned = engine.aliases.some((alias) => presentedEvidence.includes(alias));
            return (
              <article key={engine.id} className={`rounded-xl border p-3 ${engine.tone}`}>
                <div className="flex items-center justify-between gap-2">
                  <p className="text-[9px] font-mono font-bold uppercase tracking-[0.12em]">{engine.label}</p>
                  <span className={`w-1.5 h-1.5 rounded-full ${mentioned ? 'bg-current' : 'bg-border-base'}`} />
                </div>
                <p className="text-[10px] font-bold text-ink-primary mt-2">{engine.role}</p>
                <p className="text-[9px] leading-relaxed text-ink-muted mt-1">{engine.detail}</p>
                <p className="text-[8px] font-mono text-ink-muted mt-2.5">
                  {mentioned ? 'Mentioned in presented evidence' : 'No engine fields presented yet'}
                </p>
              </article>
            );
          })}
        </div>
      </div>
    </section>
  );
}
