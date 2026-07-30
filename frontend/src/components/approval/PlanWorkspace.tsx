import { useState } from 'react';
import { api } from '../../api/client';
import type { CandidatePlan, CandidatePlanSummary } from '../../types/api';
import { PlanBranchExplorer } from './PlanBranchExplorer';
import { PlanCard } from './PlanCard';

interface PlanWorkspaceProps {
  runId: string;
  plans: CandidatePlan[];
  recommendedPlanId: string | null;
  candidatePlanSummary?: CandidatePlanSummary[];
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

function CandidateComparisonTable({ summaries }: { summaries: CandidatePlanSummary[] }) {
  if (!summaries || summaries.length === 0) return null;

  // Ensure items are sorted by rank descending/ascending
  const sortedSummaries = [...summaries].sort((a, b) => a.rank - b.rank);

  return (
    <section className="rounded-2xl border border-border-base bg-abyss overflow-hidden animate-fade-up" aria-labelledby="candidate-comparison-title">
      <div className="px-5 py-4 border-b border-border-dim bg-deep/60">
        <p className="text-[8px] font-mono font-semibold uppercase tracking-[0.16em] text-ops-cyan">
          Strategy evaluation dashboard
        </p>
        <h3 id="candidate-comparison-title" className="text-base font-extrabold tracking-[-0.03em] text-ink-primary mt-1">
          Candidate Plan Comparison
        </h3>
        <p className="text-[10px] leading-relaxed text-ink-muted mt-1.5">
          AI-driven tradeoffs comparison across generated optimization strategies. Highlighted row indicates the selected recommendation.
        </p>
      </div>
      <div className="overflow-x-auto">
        <table className="w-full min-w-[920px] border-collapse">
          <caption className="sr-only">Candidate optimization plan scores and selected recommendation</caption>
          <thead>
            <tr className="border-b border-border-dim bg-deep/40 text-[9px] font-mono uppercase tracking-wider text-ink-muted">
              <th className="px-5 py-3 text-left w-16">Rank</th>
              <th className="px-5 py-3 text-left w-48">Profile</th>
              <th className="px-5 py-3 text-right w-24">Objective</th>
              <th className="px-5 py-3 text-right w-24">SLA</th>
              <th className="px-5 py-3 text-right w-24">Revenue</th>
              <th className="px-5 py-3 text-right w-24">Fairness</th>
              <th className="px-5 py-3 text-right w-24">Workload</th>
              <th className="px-5 py-3 text-left">Explanation</th>
              <th className="px-5 py-3 text-center w-32">Recommended</th>
            </tr>
          </thead>
          <tbody>
            {sortedSummaries.map((summary) => {
              const isPersonalized = summary.selected && summary.rank > 1;
              return (
                <tr 
                  key={summary.profile} 
                  className={`border-b border-border-dim/60 last:border-0 transition-colors ${
                    summary.selected 
                      ? 'bg-ops-amber/10 text-ops-amber hover:bg-ops-amber/15 font-semibold' 
                      : 'text-ink-secondary hover:bg-deep/20'
                  }`}
                >
                  <td className="px-5 py-4 text-xs font-mono">#{summary.rank}</td>
                  <td className="px-5 py-4 text-xs font-extrabold flex items-center gap-2">
                    {summary.selected && <span className="text-ops-amber text-sm">⭐</span>}
                    <span>{summary.profile}</span>
                    {isPersonalized && (
                      <span className="rounded bg-ops-violet px-2 py-0.5 text-[8px] font-bold text-white uppercase shrink-0">
                        AI Personalized
                      </span>
                    )}
                  </td>
                  <td className="px-5 py-4 text-xs font-mono text-right">{summary.objective_score.toFixed(1)}</td>
                  <td className="px-5 py-4 text-xs font-mono text-right">{summary.sla_score.toFixed(0)} / 100</td>
                  <td className="px-5 py-4 text-xs font-mono text-right">{summary.revenue_score.toFixed(0)} / 100</td>
                  <td className="px-5 py-4 text-xs font-mono text-right">{summary.fairness_score.toFixed(0)} / 100</td>
                  <td className="px-5 py-4 text-xs font-mono text-right">{summary.workload_score.toFixed(0)} / 100</td>
                  <td className="px-5 py-4 text-xs">
                    <span className={summary.selected ? "text-ops-amber" : "text-ink-muted/80"}>
                      {summary.recommendation_reason}
                    </span>
                  </td>
                  <td className="px-5 py-4 text-xs text-center">
                    {summary.selected ? (
                      <span className="rounded bg-ops-amber px-2 py-1 text-[8px] font-bold text-white uppercase">
                        AI Recommended
                      </span>
                    ) : (
                      <span className="text-[10px] text-ink-muted/40">—</span>
                    )}
                  </td>
                </tr>
              );
            })}
          </tbody>
        </table>
      </div>
    </section>
  );
}

export function PlanWorkspace({ runId, plans, recommendedPlanId, candidatePlanSummary, onApproved }: PlanWorkspaceProps) {
  const [pendingPlan, setPendingPlan] = useState<CandidatePlan | null>(null);
  const [confirmReject, setConfirmReject] = useState(false);
  const [actionInFlight, setActionInFlight] = useState<'approve' | 'reject' | null>(null);
  const [error, setError] = useState<string | null>(null);
  const sorted = sortPlans(plans, recommendedPlanId);

  const handleApprove = async () => {
    if (!pendingPlan) return;
    setActionInFlight('approve');
    setError(null);
    try {
      await api.approveRun(runId, {
        approval_status: 'APPROVED',
        recommended_plan: pendingPlan,
      });
      onApproved();
    } catch (err: unknown) {
      setError(err instanceof Error ? err.message : 'Approval failed');
      setActionInFlight(null);
    }
  };

  const handleReject = async () => {
    setActionInFlight('reject');
    setError(null);
    try {
      await api.approveRun(runId, { approval_status: 'REJECTED' });
      onApproved();
    } catch (err: unknown) {
      setError(err instanceof Error ? err.message : 'Rejection failed');
      setActionInFlight(null);
    }
  };

  return (
    <div className="animate-fade-up space-y-6">
      <div>
        <p className="text-[9px] font-mono font-semibold uppercase tracking-[0.16em] text-ops-amber">
          Human approval gate
        </p>
        <h2 className="text-xl font-extrabold tracking-[-0.035em] text-ink-primary mt-1">
          Choose a branch. Preview the consequence.
        </h2>
        <p className="text-[10px] text-ink-muted leading-relaxed max-w-2xl mt-2">
          {plans.length} feasible profiles share the same evidence and constraints. Selecting one changes only the
          preview; execution still requires a separate confirmation.
        </p>
      </div>

      {error && (
        <div className="border border-ops-rose/40 bg-ops-rose/5 rounded-lg px-4 py-3 text-sm text-ops-rose animate-fade-up" role="alert">
          Approval failed: {error}
        </div>
      )}

      {pendingPlan && (
        <section className="rounded-2xl border border-ops-amber bg-ops-amber/5 p-5 shadow-card" aria-label="Confirm plan selection">
          <p className="text-[8px] font-mono font-semibold uppercase tracking-[0.16em] text-ops-amber">
            Review before execution
          </p>
          <div className="flex flex-col lg:flex-row lg:items-center justify-between gap-5 mt-2">
            <div>
              <h3 className="text-base font-extrabold text-ink-primary">
                {profileName(pendingPlan)}
                {pendingPlan.plan_id !== recommendedPlanId && (
                  <span className="ml-2 rounded-full bg-ops-violet/10 px-2 py-1 text-[8px] font-mono uppercase text-ops-violet">
                    explicit override
                  </span>
                )}
              </h3>
              <p className="text-[10px] leading-relaxed text-ink-secondary mt-2 max-w-2xl">
                Confirming sends this exact backend plan to Core and starts SAGA execution. The selected plan is
                recorded; Core does not currently accept a separate override-reason field.
              </p>
            </div>
            <div className="flex flex-wrap gap-2 shrink-0">
              <button
                type="button"
                onClick={() => setPendingPlan(null)}
                disabled={actionInFlight !== null}
                className="rounded-lg border border-border-base bg-abyss px-4 py-2.5 text-[10px] font-semibold text-ink-secondary disabled:opacity-40 focus-ring"
              >
                Keep comparing
              </button>
              <button
                type="button"
                onClick={() => void handleApprove()}
                disabled={actionInFlight !== null}
                className="rounded-lg bg-ops-amber px-4 py-2.5 text-[10px] font-bold text-white disabled:opacity-40 focus-ring"
              >
                {actionInFlight === 'approve' ? 'Starting execution…' : 'Confirm and execute'}
              </button>
            </div>
          </div>
        </section>
      )}

      {sorted.length > 0 ? (
        <>
          <PlanBranchExplorer
            plans={sorted}
            recommendedPlanId={recommendedPlanId}
            busy={actionInFlight !== null}
            onReview={setPendingPlan}
          />

          <details className="group rounded-2xl border border-border-dim bg-deep/55">
            <summary className="cursor-pointer list-none px-5 py-4 flex items-center justify-between gap-3 text-xs font-bold text-ink-primary focus-ring rounded">
              <span>Open complete plan evidence and assignments</span>
              <span className="text-ops-cyan group-open:rotate-45 transition-transform">+</span>
            </summary>
            <div className="px-5 pb-5 pt-5 border-t border-border-dim space-y-5">
              {candidatePlanSummary && candidatePlanSummary.length > 0 && (
                <CandidateComparisonTable summaries={candidatePlanSummary} />
              )}
              <ComparisonMatrix plans={sorted} recommendedPlanId={recommendedPlanId} />
              <div>
                <div className="flex flex-wrap items-end justify-between gap-3 mb-4">
                  <div>
                    <p className="text-[8px] font-mono uppercase tracking-[0.16em] text-ink-muted">Plan evidence</p>
                    <h3 className="text-base font-extrabold tracking-[-0.03em] text-ink-primary mt-1">
                      Assignments, reasoning, and solver metadata
                    </h3>
                  </div>
                  <p className="text-[9px] text-ink-muted">Read-only backend evidence</p>
                </div>
                <div className="grid grid-cols-1 md:grid-cols-2 xl:grid-cols-4 gap-4 items-start">
                  {sorted.map((plan) => (
                    <PlanCard
                      key={plan.plan_id}
                      plan={plan}
                      isRecommended={plan.plan_id === recommendedPlanId}
                      onSelect={setPendingPlan}
                      busy={actionInFlight !== null}
                    />
                  ))}
                </div>
              </div>
            </div>
          </details>

          <details className="rounded-2xl border border-border-dim bg-deep/60">
            <summary className="cursor-pointer px-5 py-4 text-xs font-bold text-ink-primary focus-ring rounded">
              Continue manually or reject these plans
            </summary>
            <div className="px-5 pb-5 border-t border-border-dim pt-4">
              <ol className="grid sm:grid-cols-3 gap-2">
                {[
                  'Rank incidents by SLA deadline and customer impact.',
                  'Match required skills against confirmed available capacity.',
                  'Record the chosen tradeoff before changing each system.',
                ].map((step, index) => (
                  <li key={step} className="rounded-xl border border-border-dim bg-abyss p-3 text-[10px] leading-relaxed text-ink-secondary">
                    <span className="block text-[8px] font-mono text-ops-cyan mb-1">0{index + 1}</span>
                    {step}
                  </li>
                ))}
              </ol>
              <p className="text-[9px] leading-relaxed text-ink-muted mt-3">
                Goal-change instructions are not supported by the current Core contract. Reject this proposal and
                start a revised goal if the decision itself must change.
              </p>
              {!confirmReject ? (
                <button
                  type="button"
                  onClick={() => setConfirmReject(true)}
                  className="mt-4 text-[10px] font-semibold text-ops-rose hover:underline focus-ring rounded"
                >
                  Reject automated proposal
                </button>
              ) : (
                <div className="mt-4 flex flex-wrap items-center gap-3 rounded-xl border border-ops-rose/30 bg-ops-rose/5 p-3">
                  <p className="text-[10px] text-ink-secondary flex-1">
                    Rejecting ends this automated route without executing a plan.
                  </p>
                  <button type="button" onClick={() => setConfirmReject(false)} className="text-[10px] font-semibold text-ink-muted">
                    Go back
                  </button>
                  <button
                    type="button"
                    onClick={() => void handleReject()}
                    disabled={actionInFlight !== null}
                    className="rounded-lg bg-ops-rose px-3 py-2 text-[10px] font-bold text-white disabled:opacity-40"
                  >
                    {actionInFlight === 'reject' ? 'Rejecting…' : 'Confirm rejection'}
                  </button>
                </div>
              )}
            </div>
          </details>
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
