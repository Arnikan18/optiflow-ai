import { useMemo } from 'react';
import {
  deriveTeamReadiness,
  deriveTodayProblems,
} from '../../data/todayDecisionModel';
import type {
  DemoPortfolio,
  RunEvent,
  RunSummary,
} from '../../types/api';

interface CausalEvidenceMapProps {
  phaseId: string;
  events: RunEvent[];
  portfolio: DemoPortfolio | null;
  runData: RunSummary | null;
}

interface PhaseLogic {
  label: string;
  reason: string;
  alternative: string;
}

type SignalTone = 'cyan' | 'rose' | 'violet' | 'orange' | 'emerald';

interface DataSignal {
  label: string;
  value: string;
  tone: SignalTone;
}

const PHASE_LOGIC: Record<string, PhaseLogic> = {
  receive: {
    label: 'Goal received',
    reason: 'Create one traceable decision route.',
    alternative: 'Missing goal → stop',
  },
  interpret: {
    label: 'Intent understood',
    reason: 'Separate the priority from its limits.',
    alternative: 'Unclear intent → clarify',
  },
  validate: {
    label: 'Safety checked',
    reason: 'Do not plan from an unsafe assumption.',
    alternative: 'Failed guard → safe stop',
  },
  clarify: {
    label: 'Human answer recorded',
    reason: 'Resolve the missing decision before planning.',
    alternative: 'No answer → remain paused',
  },
  evidence: {
    label: 'Live evidence joined',
    reason: 'Use current clients, risks, and team capacity.',
    alternative: 'Source changes → rebuild evidence',
  },
  optimize: {
    label: 'Plans compared',
    reason: 'Test several valid trade-offs before choosing.',
    alternative: 'Different priority → different winner',
  },
  approval: {
    label: 'Human decision required',
    reason: 'Only an explicitly chosen plan may execute.',
    alternative: 'Modify → replan · Reject → close',
  },
  executing: {
    label: 'Plan applied safely',
    reason: 'Verify each operational write before continuing.',
    alternative: 'Rejected write → recover or replan',
  },
  complete: {
    label: 'Outcome verified',
    reason: 'Close only after receipts and final state agree.',
    alternative: 'Failed verification → keep route open',
  },
  failed: {
    label: 'Route stopped safely',
    reason: 'Avoid leaving hidden partial work.',
    alternative: 'Revise inputs → retry from checkpoint',
  },
};

const SIGNAL_CLASSES: Record<SignalTone, string> = {
  cyan: 'border-ops-cyan/30 bg-ops-cyan/[0.07] text-ops-cyan',
  rose: 'border-ops-rose/30 bg-ops-rose/[0.07] text-ops-rose',
  violet: 'border-ops-violet/30 bg-ops-violet/[0.07] text-ops-violet',
  orange: 'border-ops-orange/30 bg-ops-orange/[0.07] text-ops-orange',
  emerald: 'border-ops-emerald/30 bg-ops-emerald/[0.07] text-ops-emerald',
};

function Icon({
  name,
}: {
  name: 'data' | 'reason' | 'branch' | 'check';
}) {
  const paths = {
    data: (
      <>
        <ellipse cx="12" cy="5" rx="7" ry="3" />
        <path d="M5 5v7c0 1.7 3.1 3 7 3s7-1.3 7-3V5M5 12v7c0 1.7 3.1 3 7 3s7-1.3 7-3v-7" />
      </>
    ),
    reason: (
      <>
        <circle cx="12" cy="12" r="9" />
        <path d="m8 12 2.5 2.5L16.5 8" />
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
      className="w-5 h-5"
      aria-hidden="true"
    >
      {paths[name]}
    </svg>
  );
}

function formatMoney(value: number | null | undefined): string {
  if (value == null) return '—';
  return new Intl.NumberFormat('en-US', {
    style: 'currency',
    currency: 'USD',
    notation: 'compact',
    maximumFractionDigits: 1,
  }).format(value);
}

function shortEventName(eventType: string): string {
  return eventType
    .toLowerCase()
    .replace(/_/g, ' ')
    .replace(/^\w/, (letter) => letter.toUpperCase());
}

function textValue(value: unknown): string | null {
  if (typeof value === 'string' && value.trim()) return value;
  if (Array.isArray(value) && value.length > 0) {
    return value.map(String).slice(0, 3).join(' · ');
  }
  return null;
}

export function CausalEvidenceMap({
  phaseId,
  events,
  portfolio,
  runData,
}: CausalEvidenceMapProps) {
  const logic = PHASE_LOGIC[phaseId] ?? PHASE_LOGIC.receive;
  const latestEvent = events.at(-1);
  const problems = useMemo(
    () => portfolio ? deriveTodayProblems(portfolio) : [],
    [portfolio],
  );
  const workers = useMemo(
    () => portfolio ? deriveTeamReadiness(portfolio) : [],
    [portfolio],
  );

  const signals = useMemo<DataSignal[]>(() => {
    if (phaseId === 'evidence') {
      const prioritySignals = problems.slice(0, 3).map((problem) => ({
        label: problem.customer?.customer_name ?? problem.incident.incident_id,
        value: `${problem.incident.severity ?? 'Unknown'} · ${problem.deadlineLabel}`,
        tone: 'rose' as const,
      }));
      const readyWorkers = workers.filter((worker) => worker.state === 'ready').length;
      return [
        ...prioritySignals,
        {
          label: 'Team capacity',
          value: `${readyWorkers}/${workers.length} ready`,
          tone: 'cyan',
        },
      ];
    }

    if (phaseId === 'optimize' || phaseId === 'approval') {
      return (runData?.candidate_plans ?? []).slice(0, 4).map((plan) => ({
        label: plan.profile,
        value: `${plan.metrics.assigned_count} placed · ${formatMoney(plan.metrics.arr_protected)}`,
        tone: plan.plan_id === runData?.recommended_plan_id ? 'emerald' : 'violet',
      }));
    }

    if (phaseId === 'executing' || phaseId === 'complete' || phaseId === 'failed') {
      return events.slice(-4).map((event) => ({
        label: event.source.replace(/_/g, ' '),
        value: event.summary ?? shortEventName(event.event_type),
        tone: event.event_type.includes('FAIL') ? 'rose' : 'emerald',
      }));
    }

    const objective = textValue(runData?.structured_goal?.objective)
      ?? textValue(runData?.structured_goal?.objectives);
    const constraints = textValue(runData?.structured_goal?.constraints);
    const ambiguities = textValue(runData?.structured_goal?.ambiguities);
    const selectedToolCount = runData?.selected_tools.filter((tool) => tool.selected).length ?? 0;

    return [
      ...(objective ? [{ label: 'Priority', value: objective, tone: 'orange' as const }] : []),
      ...(constraints ? [{ label: 'Limits', value: constraints, tone: 'cyan' as const }] : []),
      ...(ambiguities ? [{ label: 'Needs answer', value: ambiguities, tone: 'rose' as const }] : []),
      ...(selectedToolCount > 0 ? [{
        label: 'Evidence sources',
        value: `${selectedToolCount} selected`,
        tone: 'violet' as const,
      }] : []),
    ];
  }, [events, phaseId, problems, runData, workers]);

  const recordedResult = latestEvent?.summary
    ?? (latestEvent ? shortEventName(latestEvent.event_type) : logic.label);

  return (
    <section
      id="decision-node-detail"
      className="rounded-[1.4rem] border border-border-base bg-deep/65 p-5 sm:p-6 mb-6 animate-fade-up"
      aria-labelledby="node-detail-title"
    >
      <header className="flex flex-wrap items-start justify-between gap-4">
        <div>
          <p className="text-[11px] font-mono font-semibold uppercase tracking-[0.16em] text-ops-cyan">
            Selected step
          </p>
          <h2 id="node-detail-title" className="text-xl sm:text-2xl font-extrabold tracking-[-0.035em] text-ink-primary mt-1.5">
            {logic.label}
          </h2>
        </div>
        <div className="flex items-center gap-2">
          {runData?.confidence_report && (
            <span className="rounded-full border border-ops-cyan/25 bg-ops-cyan/[0.07] px-3 py-1.5 text-[11px] font-mono font-semibold text-ops-cyan">
              {Math.round(runData.confidence_report.score)}% confidence
            </span>
          )}
          <span className="rounded-full border border-border-dim bg-abyss px-3 py-1.5 text-[11px] font-mono text-ink-muted">
            {events.length} record{events.length === 1 ? '' : 's'}
          </span>
        </div>
      </header>

      <div className="grid lg:grid-cols-[1.4fr_1fr_1fr] gap-3 mt-5">
        <article className="rounded-2xl border border-border-dim bg-abyss p-4">
          <div className="flex items-center gap-2 text-ops-cyan">
            <span className="w-9 h-9 rounded-xl bg-ops-cyan/10 flex items-center justify-center">
              <Icon name="data" />
            </span>
            <h3 className="text-sm font-extrabold text-ink-primary">Data used</h3>
          </div>
          <div className="grid sm:grid-cols-2 gap-2 mt-4">
            {signals.length > 0 ? signals.map((signal, index) => (
              <div
                key={`${signal.label}-${index}`}
                className={`rounded-xl border px-3 py-2.5 ${SIGNAL_CLASSES[signal.tone]}`}
              >
                <p className="text-[10px] font-mono font-bold uppercase tracking-[0.08em]">
                  {signal.label}
                </p>
                <p className="text-xs font-semibold leading-snug text-ink-primary mt-1">
                  {signal.value}
                </p>
              </div>
            )) : (
              <p className="text-sm text-ink-muted sm:col-span-2">Waiting for this step&apos;s data.</p>
            )}
          </div>
        </article>

        <article className="rounded-2xl border border-ops-emerald/25 bg-ops-emerald/[0.045] p-4">
          <div className="flex items-center gap-2 text-ops-emerald">
            <span className="w-9 h-9 rounded-xl bg-ops-emerald/10 flex items-center justify-center">
              <Icon name="reason" />
            </span>
            <h3 className="text-sm font-extrabold text-ink-primary">Why</h3>
          </div>
          <p className="text-base font-extrabold leading-snug text-ink-primary mt-4">
            {recordedResult}
          </p>
          <p className="text-sm leading-relaxed text-ink-secondary mt-2">
            {logic.reason}
          </p>
        </article>

        <article className="rounded-2xl border border-ops-orange/25 bg-ops-orange/[0.045] p-4">
          <div className="flex items-center gap-2 text-ops-orange">
            <span className="w-9 h-9 rounded-xl bg-ops-orange/10 flex items-center justify-center">
              <Icon name="branch" />
            </span>
            <h3 className="text-sm font-extrabold text-ink-primary">If data changes</h3>
          </div>
          <p className="text-base font-extrabold leading-snug text-ink-primary mt-4">
            {logic.alternative}
          </p>
          <div className="flex items-center gap-2 mt-4 text-xs font-semibold text-ops-orange">
            <span className="w-5 h-5 rounded-full bg-ops-orange/10 flex items-center justify-center">
              <Icon name="check" />
            </span>
            Route recalculates
          </div>
        </article>
      </div>

      <details className="group mt-4">
        <summary className="cursor-pointer list-none rounded-xl border border-border-dim bg-abyss px-4 py-3.5 flex items-center justify-between gap-3 text-sm font-bold text-ink-secondary hover:border-border-base focus-ring">
          <span>View all data</span>
          <span className="text-ops-cyan group-open:rotate-45 transition-transform text-xl leading-none">+</span>
        </summary>
        <div className="grid xl:grid-cols-3 gap-3 mt-3">
          <section className="rounded-xl border border-border-dim bg-abyss p-4">
            <h3 className="text-xs font-mono font-bold uppercase tracking-[0.12em] text-ops-rose">
              Priority incidents · {problems.length}
            </h3>
            <div className="space-y-2 mt-3">
              {problems.map((problem) => (
                <div key={problem.incident.incident_id} className="rounded-lg bg-deep px-3 py-2.5">
                  <div className="flex items-center justify-between gap-2">
                    <p className="text-sm font-bold text-ink-primary">
                      {problem.customer?.customer_name ?? problem.incident.incident_id}
                    </p>
                    <span className="text-[10px] font-mono font-bold text-ops-rose">
                      {problem.incident.severity ?? 'UNKNOWN'}
                    </span>
                  </div>
                  <p className="text-xs text-ink-muted mt-1">
                    {problem.deadlineLabel} · {problem.incident.incident_id}
                  </p>
                </div>
              ))}
              {problems.length === 0 && <p className="text-sm text-ink-muted">No active incidents.</p>}
            </div>
          </section>

          <section className="rounded-xl border border-border-dim bg-abyss p-4">
            <h3 className="text-xs font-mono font-bold uppercase tracking-[0.12em] text-ops-cyan">
              Workforce · {workers.length}
            </h3>
            <div className="space-y-2 mt-3">
              {workers.map((worker) => (
                <div key={worker.specialist.specialist_id} className="rounded-lg bg-deep px-3 py-2.5">
                  <div className="flex items-center justify-between gap-2">
                    <p className="text-sm font-bold text-ink-primary">{worker.specialist.specialist_name}</p>
                    <span className="text-[10px] font-mono font-bold uppercase text-ops-cyan">
                      {worker.state}
                    </span>
                  </div>
                  <p className="text-xs text-ink-muted mt-1">
                    {worker.remainingCapacity} free · {worker.utilisation}% used
                  </p>
                </div>
              ))}
              {workers.length === 0 && <p className="text-sm text-ink-muted">No workforce data.</p>}
            </div>
          </section>

          <section className="rounded-xl border border-border-dim bg-abyss p-4">
            <h3 className="text-xs font-mono font-bold uppercase tracking-[0.12em] text-ops-violet">
              Clients · {portfolio?.customers.length ?? 0}
            </h3>
            <div className="space-y-2 mt-3">
              {(portfolio?.customers ?? []).map((customer) => (
                <div key={customer.customer_id} className="rounded-lg bg-deep px-3 py-2.5">
                  <div className="flex items-center justify-between gap-2">
                    <p className="text-sm font-bold text-ink-primary">{customer.customer_name}</p>
                    <span className="text-xs font-semibold text-ops-violet">{formatMoney(customer.arr)}</span>
                  </div>
                  <p className="text-xs text-ink-muted mt-1">
                    {customer.current_incident_count} incident{customer.current_incident_count === 1 ? '' : 's'}
                    {customer.renewal_risk ? ' · renewal risk' : ''}
                  </p>
                </div>
              ))}
              {!portfolio?.customers.length && <p className="text-sm text-ink-muted">No client data.</p>}
            </div>
          </section>
        </div>

        <section className="rounded-xl border border-border-dim bg-abyss p-4 mt-3">
          <h3 className="text-xs font-mono font-bold uppercase tracking-[0.12em] text-ink-secondary">
            Recorded events · {events.length}
          </h3>
          <div className="space-y-2 mt-3">
            {events.map((event) => (
              <details key={event.event_id} className="rounded-lg border border-border-dim bg-deep">
                <summary className="cursor-pointer list-none px-3 py-2.5 flex items-center justify-between gap-3">
                  <span className="text-sm font-bold text-ink-primary">{shortEventName(event.event_type)}</span>
                  <span className="text-[11px] font-mono text-ink-muted">{event.source}</span>
                </summary>
                <pre className="max-h-72 overflow-auto border-t border-border-dim p-3 text-[11px] leading-relaxed text-ink-secondary">
                  {JSON.stringify(event.payload, null, 2)}
                </pre>
              </details>
            ))}
            {events.length === 0 && <p className="text-sm text-ink-muted">No records for this step yet.</p>}
          </div>
        </section>
      </details>
    </section>
  );
}
