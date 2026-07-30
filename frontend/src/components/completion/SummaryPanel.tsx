import type { RunEvent, RunSummary } from '../../types/api';

interface SummaryPanelProps {
  runData: RunSummary | null;
  events: RunEvent[];
}

interface ExecutionReceipt {
  receipt_id?: string;
  status?: string;
  actions?: string[];
  allocation?: {
    specialist_id?: string;
    incident_id?: string;
    customer_id?: string;
  };
}

function readReceipts(events: RunEvent[]): ExecutionReceipt[] {
  return events.flatMap((event) => {
    const receipts = event.payload?.receipts;
    return Array.isArray(receipts) ? receipts as ExecutionReceipt[] : [];
  });
}

function readableAction(action: string): string {
  const labels: Record<string, string> = {
    RESERVE_TENTATIVE: 'Capacity held tentatively',
    NOTIFY: 'Assignment request sent',
    CREATE_NOTIFICATION: 'Assignment request sent',
    SPECIALIST_ACCEPTED: 'Specialist accepted',
    SPECIALIST_REJECTED: 'Specialist rejected',
    SPECIALIST_TIMEOUT: 'Specialist timed out',
    RESERVE_CONFIRM: 'Capacity reservation confirmed',
    RESERVE_CANCELLED: 'Tentative reservation cancelled',
    ASSIGN: 'Incident assigned',
    ASSIGN_INCIDENT: 'Incident assigned',
  };
  return labels[action] ?? action.replace(/_/g, ' ').toLowerCase();
}

function displaySummary(value: RunSummary['business_summary']): string | null {
  if (!value) return null;
  if (typeof value === 'string') return value;
  try {
    return JSON.stringify(value, null, 2);
  } catch {
    return null;
  }
}

function ReceiptCard({ receipt }: { receipt: ExecutionReceipt }) {
  const success = receipt.status === 'SUCCESS';
  const allocation = receipt.allocation ?? {};

  return (
    <article className={`rounded-2xl border p-4 ${
      success
        ? 'border-ops-emerald/25 bg-ops-emerald/[0.045]'
        : 'border-ops-violet/30 bg-ops-violet/[0.05]'
    }`}>
      <div className="flex flex-wrap items-center justify-between gap-2">
        <span className="text-[9px] font-mono text-ink-muted">
          {receipt.receipt_id ?? 'Receipt without identifier'}
        </span>
        <span className={`rounded-full border px-2.5 py-1 text-[8px] font-mono font-semibold uppercase ${
          success
            ? 'border-ops-emerald/25 bg-ops-emerald/10 text-ops-emerald'
            : 'border-ops-violet/25 bg-ops-violet/10 text-ops-violet'
        }`}>
          {receipt.status ?? 'unknown'}
        </span>
      </div>
      <div className="grid sm:grid-cols-2 gap-3 mt-4">
        <div>
          <p className="text-[8px] font-mono uppercase tracking-[0.13em] text-ink-muted">Specialist</p>
          <p className="text-xs font-bold text-ink-primary mt-1">{allocation.specialist_id ?? 'Not reported'}</p>
        </div>
        <div>
          <p className="text-[8px] font-mono uppercase tracking-[0.13em] text-ink-muted">Incident</p>
          <p className="text-xs font-bold text-ink-primary mt-1">{allocation.incident_id ?? 'Not reported'}</p>
        </div>
      </div>
      <div className="flex flex-wrap gap-2 mt-4 pt-4 border-t border-border-dim">
        {(receipt.actions ?? []).map((action) => (
          <span key={action} className="rounded-full border border-border-dim bg-abyss px-2.5 py-1 text-[9px] text-ink-secondary">
            {readableAction(action)}
          </span>
        ))}
      </div>
    </article>
  );
}

export function SummaryPanel({ runData, events }: SummaryPanelProps) {
  const receipts = readReceipts(events);
  const successfulReceipts = receipts.filter((receipt) => receipt.status === 'SUCCESS');
  const nonSuccessReceipts = receipts.filter((receipt) => receipt.status !== 'SUCCESS');
  const latestSaga = [...events].reverse().find((event) =>
    event.event_type === 'SAGA_COMPLETED' || event.event_type === 'SAGA_FAILED');
  const sagaFailed = latestSaga?.event_type === 'SAGA_FAILED';
  const routeFailed = runData?.status === 'FAILED'
    || runData?.status === 'FAILED_SAGA'
    || sagaFailed;
  const hasVerifiedWrites = successfulReceipts.length > 0 && !sagaFailed;
  const businessSummary = displaySummary(runData?.business_summary ?? null);
  const changeSummary = displaySummary(runData?.change_summary ?? null);

  const hero = routeFailed
    ? {
        eyebrow: 'Execution review required',
        title: 'The route did not prove a successful operational outcome.',
        description:
          'Review the failed boundary and compensation evidence before retrying. A terminal run status is not treated as proof of successful writes.',
        border: 'border-ops-rose/35 bg-ops-rose/[0.055]',
        tone: 'text-ops-rose',
      }
    : hasVerifiedWrites
      ? {
          eyebrow: 'Verified execution outcome',
          title: 'Work assigned successfully.',
          description:
            `${successfulReceipts.length} verified ${successfulReceipts.length === 1 ? 'assignment was' : 'assignments were'} recorded across Workforce, Incident, and Communication.`,
          border: 'border-ops-emerald/35 bg-ops-emerald/[0.055]',
          tone: 'text-ops-emerald',
        }
      : {
          eyebrow: 'Audit route closed',
          title: 'Core closed this route without execution receipts in the visible audit stream.',
          description:
            'The decision record is available, but this screen will not claim reservations, assignments, or notifications succeeded without receipt evidence.',
          border: 'border-ops-orange/30 bg-ops-orange/[0.05]',
          tone: 'text-ops-orange',
        };

  return (
    <section className="animate-fade-up space-y-6" aria-labelledby="outcome-title">
      <div className={`rounded-[1.5rem] border p-6 sm:p-7 ${hero.border}`}>
        <p className={`text-[8px] font-mono font-semibold uppercase tracking-[0.17em] ${hero.tone}`}>
          {hero.eyebrow}
        </p>
        <h2 id="outcome-title" className="max-w-3xl text-xl sm:text-2xl font-extrabold tracking-[-0.04em] text-ink-primary mt-2">
          {hero.title}
        </h2>
        <p className="max-w-3xl text-xs sm:text-sm leading-relaxed text-ink-secondary mt-3">
          {hero.description}
        </p>
        <p className="text-[9px] font-mono text-ink-muted mt-4">Audit identity: {runData?.run_id ?? 'not reported'}</p>
      </div>

      <div className="grid grid-cols-2 lg:grid-cols-4 gap-3">
        {[
          ['Successful receipts', successfulReceipts.length],
          ['Non-success receipts', nonSuccessReceipts.length],
          ['Replans', runData?.replan_count ?? 0],
          ['Final Core status', runData?.status?.replace(/_/g, ' ') ?? 'unknown'],
        ].map(([label, value]) => (
          <div key={label} className="rounded-2xl border border-border-dim bg-deep/55 p-4">
            <p className="text-[8px] font-mono uppercase tracking-[0.13em] text-ink-muted">{label}</p>
            <p className="text-lg font-extrabold text-ink-primary mt-2">{value}</p>
          </div>
        ))}
      </div>

      {receipts.length > 0 ? (
        <div className="rounded-[1.5rem] border border-border-dim bg-abyss p-5 sm:p-6">
          <div>
            <p className="text-[8px] font-mono font-semibold uppercase tracking-[0.16em] text-ops-cyan">
              Execution receipts
            </p>
            <h3 className="text-base font-extrabold tracking-[-0.025em] text-ink-primary mt-1.5">
              What the services actually recorded
            </h3>
          </div>
          <div className="grid lg:grid-cols-2 gap-3 mt-5">
            {receipts.map((receipt, index) => (
              <ReceiptCard key={receipt.receipt_id ?? `receipt-${index}`} receipt={receipt} />
            ))}
          </div>
        </div>
      ) : (
        <div className="rounded-2xl border border-dashed border-border-base bg-deep/45 p-6">
          <p className="text-sm font-bold text-ink-primary">No execution receipt payload is available.</p>
          <p className="text-[10px] leading-relaxed text-ink-muted mt-2">
            Review the execution relay and Core logs before making an operational success claim.
          </p>
        </div>
      )}

      {(businessSummary || changeSummary) && (
        <div className="grid md:grid-cols-2 gap-3">
          {businessSummary && (
            <div className="rounded-2xl border border-border-dim bg-deep/55 p-5">
              <p className="text-[8px] font-mono font-semibold uppercase tracking-[0.14em] text-ops-cyan">Business summary</p>
              <pre className="mt-3 whitespace-pre-wrap font-sans text-[11px] leading-relaxed text-ink-secondary">{businessSummary}</pre>
            </div>
          )}
          {changeSummary && (
            <div className="rounded-2xl border border-border-dim bg-deep/55 p-5">
              <p className="text-[8px] font-mono font-semibold uppercase tracking-[0.14em] text-ops-violet">Change summary</p>
              <pre className="mt-3 whitespace-pre-wrap font-sans text-[11px] leading-relaxed text-ink-secondary">{changeSummary}</pre>
            </div>
          )}
        </div>
      )}

      <div className="rounded-2xl border border-border-dim bg-abyss p-5">
        <p className="text-[8px] font-mono font-semibold uppercase tracking-[0.16em] text-ops-amber">
          Manual verification route
        </p>
        <ol className="grid sm:grid-cols-3 gap-3 mt-4">
          {[
            'Confirm reservation status in Workforce.',
            'Confirm owner and status in Incident.',
            'Confirm assignment-request state in Communication.',
          ].map((instruction, index) => (
            <li key={instruction} className="rounded-xl border border-border-dim bg-deep/55 p-4">
              <span className="text-[8px] font-mono text-ops-amber">0{index + 1}</span>
              <p className="text-[10px] leading-relaxed text-ink-secondary mt-2">{instruction}</p>
            </li>
          ))}
        </ol>
      </div>
    </section>
  );
}
