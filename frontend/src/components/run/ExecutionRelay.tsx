import type {
  ExcludedSpecialistIncident,
  RunEvent,
  RunStatus,
  RunSummary,
} from '../../types/api';

interface ExecutionRelayProps {
  events: RunEvent[];
  runData: RunSummary | null;
  status: RunStatus | null;
}

type RelayState = 'waiting' | 'active' | 'complete' | 'reversed' | 'stopped' | 'skipped';

interface ExecutionReceipt {
  status?: string;
  actions?: string[];
  allocation?: {
    specialist_id?: string;
    incident_id?: string;
  };
}

interface RelayStep {
  number: string;
  engine: string;
  title: string;
  explanation: string;
  proof: string;
  state: RelayState;
}

const STATE_STYLE: Record<RelayState, {
  border: string;
  badge: string;
  dot: string;
  label: string;
}> = {
  waiting: {
    border: 'border-border-dim bg-deep/45',
    badge: 'border-border-base bg-abyss text-ink-muted',
    dot: 'bg-ink-ghost',
    label: 'Waiting',
  },
  active: {
    border: 'border-ops-orange/45 bg-ops-orange/[0.055] shadow-card',
    badge: 'border-ops-orange/35 bg-ops-orange/10 text-ops-orange',
    dot: 'bg-ops-orange route-pulse',
    label: 'Moving now',
  },
  complete: {
    border: 'border-ops-emerald/30 bg-ops-emerald/[0.045]',
    badge: 'border-ops-emerald/25 bg-ops-emerald/10 text-ops-emerald',
    dot: 'bg-ops-emerald',
    label: 'Recorded',
  },
  reversed: {
    border: 'border-ops-violet/35 bg-ops-violet/[0.055]',
    badge: 'border-ops-violet/25 bg-ops-violet/10 text-ops-violet',
    dot: 'bg-ops-violet',
    label: 'Safely reversed',
  },
  stopped: {
    border: 'border-ops-rose/35 bg-ops-rose/[0.055]',
    badge: 'border-ops-rose/25 bg-ops-rose/10 text-ops-rose',
    dot: 'bg-ops-rose',
    label: 'Stopped',
  },
  skipped: {
    border: 'border-border-dim bg-deep/30',
    badge: 'border-border-dim bg-abyss text-ink-ghost',
    dot: 'bg-ink-ghost',
    label: 'Not reached',
  },
};

function hasEvent(events: RunEvent[], eventType: string): boolean {
  return events.some((event) => event.event_type === eventType);
}

function payloadString(events: RunEvent[], key: string): string | null {
  for (let index = events.length - 1; index >= 0; index -= 1) {
    const value = events[index].payload?.[key];
    if (typeof value === 'string' && value.trim()) return value;
  }
  return null;
}

function readReceipts(events: RunEvent[]): ExecutionReceipt[] {
  return events.flatMap((event) => {
    const receipts = event.payload?.receipts;
    return Array.isArray(receipts) ? receipts as ExecutionReceipt[] : [];
  });
}

function describePair(pair: ExcludedSpecialistIncident): string {
  return `${pair.specialist_id} + ${pair.incident_id}`;
}

function RelayCard({ step }: { step: RelayStep }) {
  const style = STATE_STYLE[step.state];

  return (
    <article className={`animate-fade-up min-h-[258px] rounded-2xl border p-4 transition-all ${style.border}`}>
      <div className="flex items-start justify-between gap-3">
        <span className={`flex h-9 w-9 items-center justify-center rounded-xl border text-[10px] font-mono font-bold ${style.badge}`}>
          {step.state === 'complete'
            ? 'OK'
            : step.state === 'reversed'
              ? 'UNDO'
              : step.state === 'stopped'
                ? 'STOP'
                : step.number}
        </span>
        <span className={`inline-flex items-center gap-1.5 rounded-full border px-2 py-1 text-[8px] font-mono font-semibold uppercase tracking-[0.12em] ${style.badge}`}>
          <span className={`h-1.5 w-1.5 rounded-full ${style.dot}`} />
          {style.label}
        </span>
      </div>

      <p className="mt-5 text-[8px] font-mono font-semibold uppercase tracking-[0.17em] text-ink-muted">
        {step.engine}
      </p>
      <h3 className="mt-1.5 text-sm font-extrabold tracking-[-0.02em] text-ink-primary">
        {step.title}
      </h3>
      <p className="mt-2.5 text-[11px] leading-relaxed text-ink-secondary">
        {step.explanation}
      </p>

      <div className="mt-4 border-t border-border-dim pt-3">
        <p className="text-[8px] font-mono uppercase tracking-[0.14em] text-ink-muted">
          Evidence on this run
        </p>
        <p className="mt-1.5 break-words text-[10px] leading-relaxed text-ink-secondary">
          {step.proof}
        </p>
      </div>
    </article>
  );
}

export function ExecutionRelay({ events, runData, status }: ExecutionRelayProps) {
  const receipts = readReceipts(events);
  const successfulReceipt = receipts.find((receipt) => receipt.status === 'SUCCESS');
  const reversedReceipt = receipts.find((receipt) =>
    receipt.status === 'REJECTED' || receipt.status === 'TIMEOUT',
  );
  const actionSet = new Set(receipts.flatMap((receipt) => receipt.actions ?? []));

  const reserveSeen = hasEvent(events, 'SAGA_EXECUTING')
    || actionSet.has('RESERVE_TENTATIVE');
  const pollEvents = events.filter((event) => event.event_type === 'SPECIALIST_POLLING');
  const responseAccepted = hasEvent(events, 'SPECIALIST_ACCEPTED')
    || actionSet.has('SPECIALIST_ACCEPTED');
  const responseRejected = hasEvent(events, 'SPECIALIST_REJECTED')
    || Boolean(reversedReceipt);
  const sagaResolved = hasEvent(events, 'SAGA_COMPLETED')
    || hasEvent(events, 'SAGA_FAILED');
  const runCompleted = hasEvent(events, 'RUN_COMPLETED') || status === 'COMPLETED';
  const replanning = status === 'REPLANNING'
    || (runData?.replan_count ?? 0) > 0
    || (runData?.excluded_specialist_incidents.length ?? 0) > 0;
  const latestSagaOutcome = [...events].reverse().find((event) =>
    event.event_type === 'SAGA_COMPLETED' || event.event_type === 'SAGA_FAILED',
  );
  const executionFailed = latestSagaOutcome?.event_type === 'SAGA_FAILED'
    && !latestSagaOutcome.summary?.includes('REPLANNING');
  const attemptedActions = Array.isArray(latestSagaOutcome?.payload?.actions_attempted)
    ? latestSagaOutcome.payload.actions_attempted
    : [];

  const latestReceipt = successfulReceipt ?? reversedReceipt;
  const specialistId = payloadString(events, 'specialist_id')
    ?? latestReceipt?.allocation?.specialist_id
    ?? 'the selected specialist';
  const incidentId = payloadString(events, 'incident_id')
    ?? latestReceipt?.allocation?.incident_id
    ?? 'the selected incident';
  const reservationId = payloadString(events, 'reservation_id');
  const requestId = payloadString(events, 'request_id');

  const reserveState: RelayState = executionFailed
    ? 'stopped'
    : reserveSeen
      ? 'complete'
      : 'active';
  const responseState: RelayState = executionFailed && pollEvents.length === 0
    ? 'skipped'
    : responseAccepted || responseRejected
    ? 'complete'
    : reserveSeen
      ? 'active'
      : 'waiting';
  const commitState: RelayState = executionFailed && !responseAccepted && !responseRejected
    ? 'skipped'
    : responseRejected
    ? 'reversed'
    : responseAccepted
      ? 'complete'
      : pollEvents.length > 0
        ? 'active'
        : 'waiting';
  const verifyState: RelayState = sagaResolved || runCompleted
    ? 'complete'
    : responseAccepted || responseRejected
      ? 'active'
      : 'waiting';

  const steps: RelayStep[] = [
    {
      number: '01',
      engine: 'Workforce service',
      title: executionFailed ? 'Stop at the failed write boundary' : 'Hold capacity, do not commit it',
      explanation: executionFailed
        ? 'The execution engine encountered an operational conflict. Later hand-offs must not run after an earlier boundary fails.'
        : 'A tentative reservation protects this capacity from a competing run. It remains reversible until the specialist confirms.',
      proof: executionFailed
        ? latestSagaOutcome?.summary ?? 'Core recorded a SAGA execution failure.'
        : reserveSeen
        ? `${reservationId ?? 'A reservation'} now holds ${specialistId} for ${incidentId}.`
        : 'Waiting for Core to create the first tentative reservation.',
      state: reserveState,
    },
    {
      number: '02',
      engine: 'Communication service',
      title: 'Ask the specialist and wait',
      explanation: responseState === 'skipped'
        ? 'This hand-off was deliberately not reached because the earlier operational write did not succeed.'
        : 'OptiFlow sends the assignment request, then polls for an explicit acceptance. Silence is treated as a timeout, never as consent.',
      proof: responseState === 'skipped'
        ? 'No specialist response was requested during this failed attempt.'
        : pollEvents.length > 0
        ? `${requestId ?? 'The request'} has been checked ${pollEvents.length} ${pollEvents.length === 1 ? 'time' : 'times'}.`
        : reserveSeen
          ? 'Capacity is held; the response request is the next hand-off.'
          : 'No response request has been issued yet.',
      state: responseState,
    },
    {
      number: '03',
      engine: responseRejected ? 'Compensation controller' : 'Incident + workforce',
      title: commitState === 'skipped'
        ? 'Leave incident assignment untouched'
        : responseRejected
          ? 'Undo the hold and block this pairing'
          : 'Confirm both sides of the assignment',
      explanation: commitState === 'skipped'
        ? 'Without a confirmed specialist response, OptiFlow must not assign the incident or confirm a new reservation.'
        : responseRejected
        ? 'A rejection or timeout cancels the tentative reservation. The failed pair becomes a new planning constraint so it is not proposed again.'
        : 'Only an accepted response can confirm the reservation, assign the incident, and move the incident into active work.',
      proof: commitState === 'skipped'
        ? 'No successful assignment receipt exists for this attempt.'
        : responseRejected
        ? `${specialistId} was not committed to ${incidentId}; the tentative hold was reversed.`
        : responseAccepted
          ? `${specialistId} accepted ${incidentId}; reservation and incident updates were recorded.`
          : 'Waiting for an accepted, rejected, or timed-out response.',
      state: commitState,
    },
    {
      number: '04',
      engine: 'Audit + route controller',
      title: executionFailed
        ? 'Record the stop and require review'
        : replanning
          ? 'Verify the reversal and open a safer route'
          : 'Verify writes and close the route',
      explanation: executionFailed
        ? 'A SAGA failure event is evidence of an incomplete execution, not a successful mission. The UI keeps that distinction visible even if the run status later says completed.'
        : replanning
        ? 'The controller records the failed attempt, carries exclusions forward, and sends the decision back through optimisation and approval.'
        : 'Execution receipts prove which writes succeeded. Core closes the route only after the SAGA result is recorded.',
      proof: executionFailed
        ? `SAGA failure recorded; ${attemptedActions.length} downstream action(s) were attempted and ${receipts.filter((receipt) => receipt.status === 'SUCCESS').length} success receipt(s) exist.`
        : sagaResolved
        ? replanning
          ? `Replan ${runData?.replan_count ?? 1} is recorded with ${runData?.excluded_specialist_incidents.length ?? 0} excluded pairing(s).`
          : `${receipts.filter((receipt) => receipt.status === 'SUCCESS').length} successful execution receipt(s) recorded.`
        : 'Waiting for the SAGA outcome and final audit event.',
      state: verifyState,
    },
  ];

  const movingIndex = steps.findIndex((step) => step.state === 'active');
  const activeIndex = movingIndex >= 0 ? movingIndex : sagaResolved ? steps.length - 1 : 0;
  const excludedPairs = runData?.excluded_specialist_incidents ?? [];

  return (
    <section className="animate-fade-up" aria-labelledby="execution-relay-title">
      <div className={`rounded-2xl border bg-gradient-to-br via-abyss p-5 sm:p-6 ${
        executionFailed
          ? 'border-ops-rose/30 from-ops-rose/[0.09] to-ops-violet/[0.04]'
          : 'border-ops-orange/25 from-ops-orange/[0.08] to-ops-cyan/[0.05]'
      }`}>
        <div className="grid gap-4">
          <div className="max-w-2xl">
            <p className={`text-[8px] font-mono font-semibold uppercase tracking-[0.18em] ${
              executionFailed ? 'text-ops-rose' : 'text-ops-orange'
            }`}>
              {executionFailed ? 'Execution integrity alert' : 'Live execution relay'}
            </p>
            <h2 id="execution-relay-title" className="mt-2 text-lg font-extrabold tracking-[-0.035em] text-ink-primary">
              {executionFailed
                ? 'The approved change stopped before completion.'
                : 'Watch the decision become a safe operational change.'}
            </h2>
            <p className="mt-2 text-xs leading-relaxed text-ink-secondary">
              {executionFailed
                ? 'Core reported a SAGA failure. These cards separate the failed boundary from the services that were not reached, and do not claim success without a receipt.'
                : 'Each card is a real safety boundary. Data moves forward only when the previous service supplies evidence that its action succeeded.'}
            </p>
          </div>
          <div className="rounded-xl border border-border-dim bg-abyss/80 px-4 py-3">
            <p className="text-[8px] font-mono uppercase tracking-[0.14em] text-ink-muted">Current boundary</p>
            <p className={`mt-1 text-xs font-bold ${
              executionFailed ? 'text-ops-rose' : 'text-ops-orange'
            }`}>
              {steps[activeIndex]?.title ?? 'Recording outcome'}
            </p>
          </div>
        </div>

        <div className="mt-5 flex flex-wrap items-center gap-x-2 gap-y-2 text-[9px] font-mono text-ink-muted">
          {['Workforce', 'Communication', 'Incident', 'Audit'].map((engine, index) => (
            <div key={engine} className="flex items-center gap-2">
              <span className={index <= activeIndex ? 'text-ink-secondary' : 'text-ink-ghost'}>{engine}</span>
              {index < 3 && (
                <span className={index < activeIndex ? 'text-ops-emerald' : index === activeIndex ? 'text-ops-orange' : 'text-border-base'}>
                  &rarr;
                </span>
              )}
            </div>
          ))}
        </div>
      </div>

      <div className="mt-5 grid gap-3 sm:grid-cols-2">
        {steps.map((step) => (
          <RelayCard key={step.number} step={step} />
        ))}
      </div>

      <div className="mt-5 grid gap-3 md:grid-cols-2">
        <div className="rounded-2xl border border-border-dim bg-deep/55 p-5">
          <p className="text-[8px] font-mono font-semibold uppercase tracking-[0.16em] text-ops-cyan">
            {executionFailed ? 'Why this stopped' : 'Why this takes time'}
          </p>
          <h3 className="mt-1.5 text-sm font-bold text-ink-primary">
            {executionFailed ? 'Stopping is part of correctness.' : 'Waiting is part of correctness.'}
          </h3>
          <ul className="mt-3 space-y-2 text-[11px] leading-relaxed text-ink-secondary">
            {executionFailed ? (
              <>
                <li>The first conflicting write ended this attempt immediately.</li>
                <li>Communication and incident assignment were not allowed to continue.</li>
                <li>An operator can resolve the service conflict before starting a new route.</li>
              </>
            ) : (
              <>
                <li>Capacity is locked tentatively before another system is contacted.</li>
                <li>The specialist receives time to explicitly accept or reject the request.</li>
                <li>Writes happen in order so every completed action has a known reversal.</li>
              </>
            )}
          </ul>
          <p className="mt-3 border-t border-border-dim pt-3 text-[9px] leading-relaxed text-ink-muted">
            The screen also reveals events at a readable pace. This teaching delay does not slow the backend transaction.
          </p>
        </div>

        <div className={`rounded-2xl border p-5 ${
          replanning
            ? 'border-ops-violet/35 bg-ops-violet/[0.055]'
            : 'border-border-dim bg-deep/55'
        }`}>
          <p className={`text-[8px] font-mono font-semibold uppercase tracking-[0.16em] ${
            replanning ? 'text-ops-violet' : 'text-ink-muted'
          }`}>
            Recovery route
          </p>
          <h3 className="mt-1.5 text-sm font-bold text-ink-primary">
            {replanning ? 'The next plan learns from this attempt.' : 'Ready if a response fails.'}
          </h3>
          <p className="mt-2 text-[11px] leading-relaxed text-ink-secondary">
            {replanning
              ? 'Rejected and timed-out pairings are carried back to the optimiser as hard exclusions. A replacement plan still returns to you for approval.'
              : 'If a specialist rejects or times out, OptiFlow cancels the tentative hold, excludes that pairing, and generates a replacement plan.'}
          </p>
          {excludedPairs.length > 0 && (
            <div className="mt-3 flex flex-wrap gap-2">
              {excludedPairs.map((pair) => (
                <span
                  key={`${pair.specialist_id}-${pair.incident_id}`}
                  className="rounded-full border border-ops-violet/25 bg-abyss px-2.5 py-1 text-[9px] font-mono text-ops-violet"
                >
                  blocked: {describePair(pair)}
                </span>
              ))}
            </div>
          )}
        </div>
      </div>

      {executionFailed && (
        <div className="mt-5 rounded-2xl border border-ops-rose/35 bg-ops-rose/[0.055] p-5" role="alert">
          <p className="text-[8px] font-mono font-semibold uppercase tracking-[0.16em] text-ops-rose">
            Route consistency warning
          </p>
          <h3 className="mt-1.5 text-sm font-bold text-ink-primary">
            This run must not be presented as a successful mission.
          </h3>
          <p className="mt-2 text-[11px] leading-relaxed text-ink-secondary">
            The audit stream ends with a SAGA failure. Review the service conflict and compensation
            evidence before retrying; a terminal Core status alone is not proof that operational writes succeeded.
          </p>
        </div>
      )}
    </section>
  );
}
