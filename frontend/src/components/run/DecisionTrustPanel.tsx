import type { AutonomyRiskReport, ConfidenceReport } from '../../types/api';

interface DecisionTrustPanelProps {
  phaseId: string;
  confidence: ConfidenceReport | null;
  risk: AutonomyRiskReport | null;
}

const TRUST_PHASES = new Set(['optimize', 'approval', 'executing', 'complete', 'failed']);

const GRADE_EXPLANATION: Record<ConfidenceReport['grade'], string> = {
  HIGH: 'At least 90 after deterministic penalties.',
  MEDIUM: '70–89. Review the reported gaps before approval.',
  LOW: '50–69. Evidence quality needs careful human review.',
  CRITICAL: 'Below 50. Do not rely on the recommendation without correction.',
};

function formatMoney(value: number): string {
  return new Intl.NumberFormat('en-US', {
    style: 'currency',
    currency: 'USD',
    maximumFractionDigits: 0,
  }).format(value);
}

function Metric({
  label,
  value,
  detail,
  tone,
}: {
  label: string;
  value: string;
  detail: string;
  tone: string;
}) {
  return (
    <div className="rounded-xl border border-border-dim bg-abyss p-3.5">
      <p className="text-[8px] font-mono uppercase tracking-[0.14em] text-ink-muted">{label}</p>
      <p className={`text-xl font-extrabold tracking-[-0.045em] mt-1.5 ${tone}`}>{value}</p>
      <p className="text-[9px] leading-relaxed text-ink-muted mt-1">{detail}</p>
    </div>
  );
}

export function DecisionTrustPanel({
  phaseId,
  confidence,
  risk,
}: DecisionTrustPanelProps) {
  if (!TRUST_PHASES.has(phaseId)) return null;

  if (!confidence && !risk) {
    return (
      <section className="rounded-2xl border border-dashed border-border-base bg-deep/50 px-4 py-4 mb-6">
        <p className="text-[8px] font-mono font-semibold uppercase tracking-[0.16em] text-ops-violet">
          Decision trust
        </p>
        <p className="text-xs font-semibold text-ink-primary mt-1.5">
          Quality and autonomy reports are not available yet.
        </p>
        <p className="text-[10px] leading-relaxed text-ink-muted mt-1">
          This panel will use the backend’s deterministic confidence penalties and approval-risk report when supplied.
        </p>
      </section>
    );
  }

  const score = confidence?.score ?? 0;
  const grade = confidence?.grade ?? 'CRITICAL';
  const penalties = confidence
    ? [
        ['Freshness', confidence.freshness_penalty],
        ['Completeness', confidence.completeness_penalty],
        ['Conflicts', confidence.conflict_penalty],
      ] as const
    : [];

  return (
    <section className="rounded-2xl border border-border-base bg-abyss overflow-hidden mb-6" aria-labelledby="decision-trust-title">
      <div className="px-4 sm:px-5 py-4 border-b border-border-dim bg-deep/60 flex flex-wrap items-start justify-between gap-3">
        <div>
          <p className="text-[8px] font-mono font-semibold uppercase tracking-[0.17em] text-ops-violet">
            Decision trust
          </p>
          <h2 id="decision-trust-title" className="text-sm font-extrabold tracking-[-0.025em] text-ink-primary mt-1">
            Why this recommendation deserves—or needs—scrutiny
          </h2>
        </div>
        <span className="rounded-full border border-border-dim bg-abyss px-2.5 py-1 text-[8px] font-mono text-ink-muted">
          Backend supplied values
        </span>
      </div>

      {confidence && (
        <div className="p-4 sm:p-5 border-b border-border-dim">
          <div className="grid sm:grid-cols-2 xl:grid-cols-4 gap-2">
            <Metric
              label="Confidence"
              value={`${score.toFixed(1)}/100`}
              detail={GRADE_EXPLANATION[grade]}
              tone={grade === 'HIGH' ? 'text-ops-emerald' : grade === 'CRITICAL' ? 'text-ops-rose' : 'text-ops-amber'}
            />
            <Metric
              label="Reported data age"
              value={`${confidence.freshness_age_hours.toFixed(2)}h`}
              detail="Age value used by the quality report."
              tone="text-ops-cyan"
            />
            <Metric
              label="Missing fields"
              value={String(confidence.missing_field_count)}
              detail={`${confidence.completeness_penalty} confidence points deducted.`}
              tone={confidence.missing_field_count > 0 ? 'text-ops-orange' : 'text-ops-emerald'}
            />
            <Metric
              label="Conflicts"
              value={String(confidence.conflict_count)}
              detail={`${confidence.conflict_penalty} confidence points deducted.`}
              tone={confidence.conflict_count > 0 ? 'text-ops-rose' : 'text-ops-emerald'}
            />
          </div>

          <div className="grid lg:grid-cols-[minmax(0,1fr)_280px] gap-5 mt-5">
            <div>
              <div className="flex items-center justify-between gap-4 text-[9px] font-mono">
                <span className="text-ink-muted">Quality score after penalties</span>
                <span className="font-semibold text-ink-primary">
                  100 − {confidence.total_penalty} = {score.toFixed(1)}
                </span>
              </div>
              <div className="h-2.5 rounded-full bg-surface overflow-hidden mt-2">
                <div
                  className={`h-full rounded-full ${grade === 'HIGH' ? 'bg-ops-emerald' : grade === 'CRITICAL' ? 'bg-ops-rose' : 'bg-ops-amber'}`}
                  style={{ width: `${Math.max(0, Math.min(score, 100))}%` }}
                />
              </div>
              <p className="text-[9px] leading-relaxed text-ink-muted mt-2">
                Confidence measures evidence quality, not the probability that a business outcome will succeed.
              </p>
            </div>

            <div className="space-y-2">
              {penalties.map(([label, value]) => (
                <div key={label} className="flex items-center justify-between rounded-lg bg-deep px-3 py-2">
                  <span className="text-[9px] text-ink-muted">{label} penalty</span>
                  <span className={`text-[9px] font-mono font-semibold ${value > 0 ? 'text-ops-orange' : 'text-ops-emerald'}`}>
                    −{value}
                  </span>
                </div>
              ))}
            </div>
          </div>

          {confidence.freshness_age_hours === 0 && (
            <p className="text-[9px] leading-relaxed text-ink-muted mt-4">
              A reported age of 0h means no freshness penalty was returned. The current report does not distinguish
              a truly zero-age snapshot from an unavailable age value.
            </p>
          )}
        </div>
      )}

      {risk && (
        <div className="p-4 sm:p-5">
          <div className="grid sm:grid-cols-3 gap-2">
            <Metric
              label="Autonomy risk"
              value={risk.risk_level}
              detail="Determines the level of human scrutiny required."
              tone={risk.risk_level === 'HIGH' ? 'text-ops-rose' : 'text-ops-emerald'}
            />
            <Metric
              label="ARR exposure"
              value={formatMoney(risk.total_arr_exposure)}
              detail="Annual recurring revenue of affected customers."
              tone="text-ops-violet"
            />
            <Metric
              label="Planned allocations"
              value={String(risk.allocation_count)}
              detail={`${risk.affected_customers.length} customer${risk.affected_customers.length === 1 ? '' : 's'} affected.`}
              tone="text-ops-cyan"
            />
          </div>

          <div className={`rounded-xl border p-4 mt-4 ${
            risk.risk_level === 'HIGH'
              ? 'border-ops-rose/30 bg-ops-rose/5'
              : 'border-ops-emerald/30 bg-ops-emerald/5'
          }`}>
            <p className={`text-[8px] font-mono uppercase tracking-[0.14em] ${
              risk.risk_level === 'HIGH' ? 'text-ops-rose' : 'text-ops-emerald'
            }`}>
              Why approval is required
            </p>
            <ul className="space-y-2 mt-2.5">
              {risk.reasons.map((reason) => (
                <li key={reason} className="flex gap-2 text-[10px] leading-relaxed text-ink-secondary">
                  <span aria-hidden="true">→</span>
                  {reason}
                </li>
              ))}
            </ul>
          </div>

          <p className="text-[9px] leading-relaxed text-ink-muted mt-3">
            ARR exposure is context for approval. It is not a prediction that this revenue will be lost.
          </p>
        </div>
      )}
    </section>
  );
}
