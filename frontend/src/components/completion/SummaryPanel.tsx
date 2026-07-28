import type { RunSummary, RunEvent } from '../../types/api';

interface SummaryPanelProps {
  runData: RunSummary | null;
  events: RunEvent[];
}

function ReceiptCard({ event }: { event: RunEvent }) {
  const time = event.received_at
    ? new Date(event.received_at).toLocaleTimeString()
    : '';

  return (
    <div className="flex items-start gap-3 py-3 border-b border-border-dim last:border-0 animate-scan-in">
      <div className="w-2 h-2 rounded-full bg-ops-emerald mt-1.5 shrink-0" />
      <div className="flex-1 min-w-0">
        <p className="text-xs font-mono text-ops-emerald uppercase tracking-wider">
          {event.event_type.replace(/_/g, ' ')}
        </p>
        {event.summary && (
          <p className="text-sm text-ink-secondary mt-0.5 leading-relaxed">{event.summary}</p>
        )}
      </div>
      <span className="text-xs font-mono text-ink-muted shrink-0">{time}</span>
    </div>
  );
}

export function SummaryPanel({ runData, events }: SummaryPanelProps) {
  const isFailed = runData?.status === 'FAILED';

  const completionEvents = events.filter((e) =>
    ['RUN_COMPLETED', 'PLAN_APPROVED', 'SAGA_EXECUTING', 'RUN_FAILED'].includes(e.event_type),
  );

  const allocationEvents = events.filter((e) =>
    e.event_type.startsWith('SAGA') || e.event_type.includes('ASSIGN') || e.event_type.includes('RESERVE'),
  );

  return (
    <div className="animate-fade-up space-y-6 max-w-3xl mx-auto">
      {/* Hero status */}
      <div
        className={`rounded-2xl border p-6 text-center space-y-3
          ${isFailed
            ? 'border-ops-rose/40 bg-ops-rose/8'
            : 'border-ops-emerald/40 bg-ops-emerald/8 glow-emerald'
          }`}
      >
        <div className="text-5xl">{isFailed ? '❌' : '✅'}</div>
        <h2 className="text-xl font-bold text-ink-primary">
          {isFailed ? 'Execution Failed' : 'Mission Complete'}
        </h2>
        <p className="text-sm text-ink-secondary max-w-lg mx-auto leading-relaxed">
          {isFailed
            ? 'The SAGA transaction was rolled back. No partial changes were committed. Review the error details below and retry from the Control Room.'
            : 'All allocation changes have been successfully committed to enterprise systems. The full audit trail is now closed and permanently stored.'
          }
        </p>
        <div className="flex items-center justify-center gap-2 font-mono text-xs text-ink-muted">
          <span>Run ID:</span>
          <span className="text-ink-secondary">{runData?.run_id ?? '—'}</span>
        </div>
      </div>

      {/* What this means — education block */}
      {!isFailed && (
        <div className="grid grid-cols-1 sm:grid-cols-3 gap-4">
          {[
            {
              icon: '🔗',
              title: 'Audit Trail Closed',
              desc: 'Every decision in this session — goal, evidence, plans, approval, execution — is permanently recorded and linked to the Run ID.',
            },
            {
              icon: '📋',
              title: 'Specialists Assigned',
              desc: 'Workforce reservations have been committed. Specialists are now allocated to their approved incidents in the system.',
            },
            {
              icon: '🔔',
              title: 'Notifications Dispatched',
              desc: 'Assignment notifications have been sent to affected specialists and customers through the Communication service.',
            },
          ].map(({ icon, title, desc }) => (
            <div key={title} className="bg-deep border border-border-dim rounded-xl p-4 space-y-2">
              <span className="text-2xl">{icon}</span>
              <p className="text-sm font-semibold text-ink-primary">{title}</p>
              <p className="text-xs text-ink-muted leading-relaxed">{desc}</p>
            </div>
          ))}
        </div>
      )}

      {/* Execution log */}
      {allocationEvents.length > 0 && (
        <div className="bg-deep border border-border-dim rounded-xl p-5">
          <p className="text-xs font-mono text-ink-secondary uppercase tracking-widest mb-4">
            Execution Receipts
          </p>
          <div>
            {allocationEvents.map((e) => (
              <ReceiptCard key={e.event_id} event={e} />
            ))}
          </div>
        </div>
      )}

      {/* All run events (collapsed) */}
      {completionEvents.length > 0 && (
        <div className="bg-deep border border-border-dim rounded-xl p-5">
          <p className="text-xs font-mono text-ink-secondary uppercase tracking-widest mb-4">
            Terminal Events
          </p>
          {completionEvents.map((e) => (
            <ReceiptCard key={e.event_id} event={e} />
          ))}
        </div>
      )}

      {/* Learning callout */}
      <div className="bg-abyss border border-border-dim rounded-xl p-5 space-y-3">
        <p className="text-xs font-mono text-ops-amber uppercase tracking-widest">
          Decision-Making Without the AI
        </p>
        <p className="text-sm text-ink-secondary leading-relaxed">
          Even when the AI is unavailable, you can replicate this process manually: query CRM for ARR and tier data, query Incident for SLA deadlines, query Workforce for availability, then score allocations against the same objectives. The system's value is in doing this at scale and in parallel — but the decision logic remains yours.
        </p>
        <p className="text-sm text-ink-secondary leading-relaxed">
          The four profiles you compared (Balanced, SLA-First, Revenue-First, Fairness-First) represent real trade-off dimensions every operations manager faces. Understanding which profile you chose and why is the most important skill this system teaches.
        </p>
      </div>
    </div>
  );
}
