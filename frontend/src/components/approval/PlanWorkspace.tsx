import { useState } from 'react';
import { api } from '../../api/client';
import type { CandidatePlan } from '../../types/api';
import { PlanCard } from './PlanCard';

interface PlanWorkspaceProps {
  runId: string;
  plans: CandidatePlan[];
  recommendedPlanId: string | null;
  onApproved: () => void;
}

interface ComparisonMetric {
  label: string;
  explanation: string;
  direction: 'higher' | 'lower';
  read: (plan: CandidatePlan) => number | null;
  format: (value: number) => string;
}

const PROFILE_FOCUS: Record<string, string> = {
  Balanced: 'Balances service, revenue, and team load.',
  'SLA-First': 'Prioritises time-critical service coverage.',
  'Revenue-First': 'Prioritises ARR protection and customer value.',
  'Fairness-First': 'Prioritises equitable workload distribution.',
};

function profileName(plan: CandidatePlan): string {
  return plan.profile_name ?? plan.profile;
}

function sortPlans(plans: CandidatePlan[], recommendedId: string | null): CandidatePlan[] {
  return [...plans].sort((left, right) => {
    if (left.plan_id === recommendedId) return -1;
    if (right.plan_id === recommendedId) return 1;
    return 0;
  });
}

function asNumber(value: unknown): number | null {
  return typeof value === 'number' && Number.isFinite(value) ? value : null;
}

function percent(value: number): string {
  const normalized = value <= 1 ? value * 100 : value;
  return `${normalized.toFixed(1)}%`;
}

function money(value: number): string {
  return new Intl.NumberFormat('en-US', {
    style: 'currency',
    currency: 'USD',
    notation: value >= 1_000_000 ? 'compact' : 'standard',
    maximumFractionDigits: 0,
  }).format(value);
}

const COMPARISON_METRICS: ComparisonMetric[] = [
  {
    label: 'Match rate',
    explanation: 'Share of required work receiving a viable assignment.',
    direction: 'higher',
    read: (plan) => asNumber(plan.metrics.match_rate),
    format: percent,
  },
  {
    label: 'ARR protected',
    explanation: 'Annual recurring revenue represented by covered customer work.',
    direction: 'higher',
    read: (plan) => asNumber(plan.metrics.arr_protected),
    format: money,
  },
  {
    label: 'Assigned work',
    explanation: 'Number of incidents receiving a specialist.',
    direction: 'higher',
    read: (plan) => asNumber(plan.metrics.assigned_count),
    format: String,
  },
  {
    label: 'Unassigned work',
    explanation: 'Incidents left without an assignment in this plan.',
    direction: 'lower',
    read: (plan) => asNumber(plan.metrics.unassigned_count),
    format: String,
  },
  {
    label: 'SLA breaches avoided',
    explanation: 'Count of predicted SLA breaches the plan reports avoiding.',
    direction: 'higher',
    read: (plan) => asNumber(plan.metrics.sla_breaches_avoided),
    format: String,
  },
  {
    label: 'Fairness score',
    explanation: 'Backend score for how evenly work is distributed.',
    direction: 'higher',
    read: (plan) => asNumber(plan.metrics.fairness_score),
    format: percent,
  },
  {
    label: 'Context switches',
    explanation: 'Reported specialist context changes introduced by the plan.',
    direction: 'lower',
    read: (plan) => asNumber(plan.metrics.context_switching_count),
    format: String,
  },
  {
    label: 'Maximum utilisation',
    explanation: 'Highest reported utilisation for any one specialist.',
    direction: 'lower',
    read: (plan) => asNumber(plan.metrics.maximum_specialist_utilisation),
    format: percent,
  },
];

function ComparisonMatrix({
  plans,
  recommendedPlanId,
}: {
  plans: CandidatePlan[];
  recommendedPlanId: string | null;
}) {
  const visibleMetrics = COMPARISON_METRICS.filter((metric) =>
    plans.some((plan) => metric.read(plan) !== null),
  );

  return (
    <section className="rounded-2xl border border-border-base bg-abyss overflow-hidden" aria-labelledby="plan-comparison-title">
      <div className="px-5 py-4 border-b border-border-dim bg-deep/60">
        <p className="text-[8px] font-mono font-semibold uppercase tracking-[0.16em] text-ops-cyan">
          Side-by-side decision matrix
        </p>
        <h3 id="plan-comparison-title" className="text-base font-extrabold tracking-[-0.03em] text-ink-primary mt-1">
          See what each profile wins—and what it gives up
        </h3>
        <p className="text-[10px] leading-relaxed text-ink-muted mt-1.5">
          “Best” marks the strongest supplied value for that row, not a universally best plan.
        </p>
      </div>

      <div className="overflow-x-auto">
        <table className="w-full min-w-[820px] border-collapse">
          <caption className="sr-only">
            Comparison of candidate allocation plan metrics and tradeoffs
          </caption>
          <thead>
            <tr>
              <th className="w-48 px-4 py-4 text-left border-b border-r border-border-dim bg-deep">
                <span className="text-[8px] font-mono uppercase tracking-[0.14em] text-ink-muted">Metric</span>
              </th>
              {plans.map((plan) => {
                const name = profileName(plan);
                const recommended = plan.plan_id === recommendedPlanId;
                return (
                  <th key={plan.plan_id} className={`min-w-40 px-4 py-4 text-left border-b border-r last:border-r-0 border-border-dim ${recommended ? 'bg-ops-amber/5' : 'bg-deep'}`}>
                    <div className="flex items-center gap-2">
                      <span className="text-xs font-extrabold text-ink-primary">{name}</span>
                      {recommended && (
                        <span className="rounded-full bg-ops-amber px-2 py-1 text-[7px] font-mono uppercase text-white">
                          recommended
                        </span>
                      )}
                    </div>
                    <p className="text-[9px] font-normal leading-relaxed text-ink-muted mt-2">
                      {PROFILE_FOCUS[name] ?? plan.description}
                    </p>
                  </th>
                );
              })}
            </tr>
          </thead>
          <tbody>
            {visibleMetrics.map((metric) => {
              const values = plans.map(metric.read);
              const supplied = values.filter((value): value is number => value !== null);
              const best = supplied.length > 0
                ? (metric.direction === 'higher' ? Math.max(...supplied) : Math.min(...supplied))
                : null;

              return (
                <tr key={metric.label}>
                  <th scope="row" className="px-4 py-3 text-left border-b border-r border-border-dim bg-deep/60">
                    <span className="block text-[10px] font-bold text-ink-secondary">{metric.label}</span>
                    <span className="block text-[8px] font-normal leading-relaxed text-ink-muted mt-1">
                      {metric.explanation}
                    </span>
                  </th>
                  {plans.map((plan, index) => {
                    const value = values[index];
                    const winner = value !== null && value === best;
                    return (
                      <td key={plan.plan_id} className={`px-4 py-3 border-b border-r last:border-r-0 border-border-dim ${winner ? 'bg-ops-emerald/5' : ''}`}>
                        <div className="flex items-center justify-between gap-2">
                          <span className={`text-xs font-mono font-semibold ${winner ? 'text-ops-emerald' : 'text-ink-secondary'}`}>
                            {value === null ? '—' : metric.format(value)}
                          </span>
                          {winner && supplied.length > 1 && (
                            <span className="text-[7px] font-mono uppercase tracking-wider text-ops-emerald">best</span>
                          )}
                        </div>
                      </td>
                    );
                  })}
                </tr>
              );
            })}
            <tr>
              <th scope="row" className="px-4 py-3 text-left border-r border-border-dim bg-deep/60">
                <span className="block text-[10px] font-bold text-ink-secondary">Solver truth</span>
                <span className="block text-[8px] font-normal text-ink-muted mt-1">Status, engine, and actual solve time.</span>
              </th>
              {plans.map((plan) => (
                <td key={plan.plan_id} className="px-4 py-3 border-r last:border-r-0 border-border-dim">
                  <p className="text-[9px] font-mono font-semibold text-ink-primary">{plan.metadata.solver_status}</p>
                  <p className="text-[8px] text-ink-muted mt-1">
                    {plan.metadata.solver_type} · {plan.metadata.solving_time_ms}ms
                    {plan.metadata.fallback_status ? ' · fallback' : ''}
                  </p>
                </td>
              ))}
            </tr>
          </tbody>
        </table>
      </div>
    </section>
  );
}

export function PlanWorkspace({ runId, plans, recommendedPlanId, onApproved }: PlanWorkspaceProps) {
  const [approving, setApproving] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const sorted = sortPlans(plans, recommendedPlanId);

  const handleApprove = async (plan: CandidatePlan) => {
    setApproving(true);
    setError(null);
    try {
      await api.approveRun(runId, {
        approval_status: 'APPROVED',
        recommended_plan: plan,
      });
      onApproved();
    } catch (err: unknown) {
      setError(err instanceof Error ? err.message : 'Approval failed');
      setApproving(false);
    }
  };

  return (
    <div className="animate-fade-up space-y-6">
      <div>
        <p className="text-[9px] font-mono font-semibold uppercase tracking-[0.16em] text-ops-amber">
          Human approval gate
        </p>
        <h2 className="text-xl font-extrabold tracking-[-0.035em] text-ink-primary mt-1">
          Choose the tradeoff you can defend.
        </h2>
        <p className="text-sm text-ink-secondary leading-relaxed max-w-3xl mt-2">
          The planning engines produced {plans.length} candidate plans from the same constraints. Compare their
          measurable outcomes, inspect their reasoning, and approve one. No enterprise write has happened yet.
        </p>
      </div>

      {error && (
        <div className="border border-ops-rose/40 bg-ops-rose/5 rounded-lg px-4 py-3 text-sm text-ops-rose animate-fade-up" role="alert">
          Approval failed: {error}
        </div>
      )}

      {sorted.length > 0 ? (
        <>
          <ComparisonMatrix plans={sorted} recommendedPlanId={recommendedPlanId} />
          <div>
            <div className="flex flex-wrap items-end justify-between gap-3 mb-4">
              <div>
                <p className="text-[8px] font-mono uppercase tracking-[0.16em] text-ink-muted">Plan details</p>
                <h3 className="text-base font-extrabold tracking-[-0.03em] text-ink-primary mt-1">
                  Inspect assignments and reasoning before approval
                </h3>
              </div>
              <p className="text-[9px] text-ink-muted">Approving one plan starts SAGA execution.</p>
            </div>
            <div className="grid grid-cols-1 md:grid-cols-2 xl:grid-cols-4 gap-4 items-start">
              {sorted.map((plan) => (
                <PlanCard
                  key={plan.plan_id}
                  plan={plan}
                  isRecommended={plan.plan_id === recommendedPlanId}
                  onApprove={handleApprove}
                  approving={approving}
                />
              ))}
            </div>
          </div>
        </>
      ) : (
        <div className="border border-border-dim rounded-xl p-12 text-center">
          <span className="mx-auto block w-5 h-5 rounded-full border-2 border-ops-cyan/30 border-t-ops-cyan animate-spin" />
          <p className="text-sm font-semibold text-ink-secondary mt-4">Generating candidate plans</p>
          <p className="text-xs text-ink-muted font-mono mt-1">Waiting for solver results from the backend.</p>
        </div>
      )}
    </div>
  );
}
