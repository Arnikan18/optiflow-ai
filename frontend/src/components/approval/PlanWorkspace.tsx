import { useEffect, useMemo, useState } from 'react';
import { api } from '../../api/client';
import type { CandidatePlan, CandidatePlanSummary } from '../../types/api';

interface PlanWorkspaceProps {
  runId: string;
  plans: CandidatePlan[];
  recommendedPlanId: string | null;
  candidatePlanSummary?: CandidatePlanSummary[];
  onApproved: () => void;
}

const PROFILE_FOCUS: Record<string, string> = {
  Balanced: 'Balances customer impact, SLA risk, and team load.',
  'SLA-First': 'Protects the most time-critical service commitments.',
  'SLA First': 'Protects the most time-critical service commitments.',
  'Revenue-First': 'Protects the greatest customer and revenue exposure.',
  'Revenue First': 'Protects the greatest customer and revenue exposure.',
  'Fairness-First': 'Distributes work more evenly across the available team.',
  'Fairness First': 'Distributes work more evenly across the available team.',
};

const PROFILE_TONE: Record<string, string> = {
  Balanced: 'border-ops-cyan/35 bg-ops-cyan/[0.06] text-ops-cyan',
  'SLA-First': 'border-ops-rose/35 bg-ops-rose/[0.06] text-ops-rose',
  'SLA First': 'border-ops-rose/35 bg-ops-rose/[0.06] text-ops-rose',
  'Revenue-First': 'border-ops-emerald/35 bg-ops-emerald/[0.06] text-ops-emerald',
  'Revenue First': 'border-ops-emerald/35 bg-ops-emerald/[0.06] text-ops-emerald',
  'Fairness-First': 'border-ops-violet/35 bg-ops-violet/[0.06] text-ops-violet',
  'Fairness First': 'border-ops-violet/35 bg-ops-violet/[0.06] text-ops-violet',
};

function profileName(plan: CandidatePlan): string {
  return plan.profile_name ?? plan.profile;
}

function normalizedProfile(value: string): string {
  return value.toLowerCase().replace(/[^a-z]/g, '');
}

function summaryFor(
  plan: CandidatePlan,
  summaries: CandidatePlanSummary[],
): CandidatePlanSummary | null {
  const profile = normalizedProfile(profileName(plan));
  return summaries.find((summary) => normalizedProfile(summary.profile) === profile) ?? null;
}

function sortPlans(plans: CandidatePlan[], recommendedPlanId: string | null): CandidatePlan[] {
  return [...plans].sort((left, right) => {
    if (left.plan_id === recommendedPlanId) return -1;
    if (right.plan_id === recommendedPlanId) return 1;
    return right.objective_value - left.objective_value;
  });
}

function metricNumber(plan: CandidatePlan, key: string): number | null {
  const value = plan.metrics[key];
  return typeof value === 'number' && Number.isFinite(value) ? value : null;
}

function percent(value: number | null): string {
  if (value === null) return '—';
  return `${Math.round(value <= 1 ? value * 100 : value)}%`;
}

function count(value: number | null): string {
  return value === null ? '—' : Math.round(value).toString();
}

function money(value: number | null): string {
  if (value === null) return '—';
  return new Intl.NumberFormat('en-US', {
    style: 'currency',
    currency: 'USD',
    notation: 'compact',
    maximumFractionDigits: 1,
  }).format(value);
}

function preferenceLabel(summary: CandidatePlanSummary | null): string {
  if (!summary?.selected) return 'AI option';
  return summary.rank > 1 ? 'Personalized choice' : 'AI recommended';
}

function preferenceReason(
  plan: CandidatePlan,
  summary: CandidatePlanSummary | null,
): string {
  return summary?.recommendation_reason
    ?? plan.explanation
    ?? PROFILE_FOCUS[profileName(plan)]
    ?? plan.description;
}

function PlanMetrics({
  plan,
  summary,
}: {
  plan: CandidatePlan;
  summary: CandidatePlanSummary | null;
}) {
  const metrics = [
    {
      label: 'SLA',
      value: summary ? `${Math.round(summary.sla_score)}` : percent(metricNumber(plan, 'sla_score')),
    },
    {
      label: 'Revenue',
      value: summary ? `${Math.round(summary.revenue_score)}` : money(metricNumber(plan, 'arr_protected')),
    },
    {
      label: 'Fairness',
      value: summary ? `${Math.round(summary.fairness_score)}` : percent(metricNumber(plan, 'fairness_score')),
    },
    {
      label: 'Covered',
      value: count(metricNumber(plan, 'assigned_count')),
    },
  ];

  return (
    <div className="grid grid-cols-2 sm:grid-cols-4 gap-2">
      {metrics.map((metric) => (
        <div key={metric.label} className="rounded-xl border border-border-dim bg-deep px-4 py-3">
          <p className="text-xl font-extrabold text-ink-primary">{metric.value}</p>
          <p className="text-sm text-ink-muted mt-1">{metric.label}</p>
        </div>
      ))}
    </div>
  );
}

function AlternativeCard({
  plan,
  summary,
  busy,
  onSelect,
}: {
  plan: CandidatePlan;
  summary: CandidatePlanSummary | null;
  busy: boolean;
  onSelect: (plan: CandidatePlan) => void;
}) {
  const profile = profileName(plan);
  const tone = PROFILE_TONE[profile] ?? PROFILE_TONE.Balanced;
  const feasible = plan.feasible
    ?? plan.metadata.feasibility
    ?? plan.metadata.solver_status !== 'INFEASIBLE';

  return (
    <article className="rounded-2xl border border-border-dim bg-deep p-4">
      <div className="flex items-start justify-between gap-3">
        <div>
          <p className="text-lg font-extrabold text-ink-primary">{profile}</p>
          <p className="text-sm leading-relaxed text-ink-muted mt-1">
            {PROFILE_FOCUS[profile] ?? plan.description}
          </p>
        </div>
        <span className={`shrink-0 rounded-full border px-3 py-1 text-sm font-bold ${tone}`}>
          {summary ? `#${summary.rank}` : 'Option'}
        </span>
      </div>

      <div className="flex items-center justify-between gap-3 mt-4 pt-4 border-t border-border-dim">
        <div className="flex gap-4 text-sm">
          <span className="text-ink-muted">
            Covered <strong className="text-ink-primary">{count(metricNumber(plan, 'assigned_count'))}</strong>
          </span>
          <span className="text-ink-muted">
            Waiting <strong className="text-ink-primary">{count(metricNumber(plan, 'unassigned_count'))}</strong>
          </span>
        </div>
        <button
          type="button"
          disabled={busy || !feasible}
          onClick={() => onSelect(plan)}
          className="rounded-xl border border-border-base bg-abyss px-4 py-2.5 text-sm font-bold text-ink-primary hover:border-ops-violet hover:text-ops-violet disabled:opacity-40 focus-ring"
        >
          Choose
        </button>
      </div>
    </article>
  );
}

function PlanEvidence({
  plans,
  recommendedPlanId,
}: {
  plans: CandidatePlan[];
  recommendedPlanId: string | null;
}) {
  return (
    <details className="group rounded-2xl border border-border-dim bg-deep">
      <summary className="cursor-pointer list-none px-5 py-4 flex items-center justify-between gap-3 text-base font-bold text-ink-primary focus-ring rounded-2xl">
        <span>View plan evidence and assignments</span>
        <span className="text-ops-cyan group-open:rotate-45 transition-transform">+</span>
      </summary>
      <div className="border-t border-border-dim p-5 space-y-3">
        {plans.map((plan) => {
          const allocations = plan.assignments.length ? plan.assignments : plan.allocations;
          return (
            <details key={plan.plan_id} className="rounded-xl border border-border-dim bg-abyss">
              <summary className="cursor-pointer list-none px-4 py-3 flex items-center justify-between gap-3 focus-ring rounded-xl">
                <span className="text-base font-bold text-ink-primary">{profileName(plan)}</span>
                <span className="text-sm text-ink-muted">
                  {plan.plan_id === recommendedPlanId ? 'Recommended · ' : ''}
                  {allocations.length} assignments
                </span>
              </summary>
              <div className="border-t border-border-dim px-4 py-4">
                <p className="text-sm leading-relaxed text-ink-secondary whitespace-pre-wrap">
                  {plan.explanation || plan.description}
                </p>
                <div className="grid sm:grid-cols-2 gap-2 mt-4">
                  {allocations.map((allocation) => (
                    <div
                      key={`${allocation.incident_id}-${allocation.specialist_id}`}
                      className="rounded-lg border border-border-dim bg-deep px-3 py-2 text-sm"
                    >
                      <span className="font-bold text-ink-primary">{allocation.incident_id}</span>
                      <span className="text-ink-muted"> → </span>
                      <span className="text-ops-cyan">{allocation.specialist_id}</span>
                    </div>
                  ))}
                  {!allocations.length && (
                    <p className="text-sm text-ink-muted">No assignments in this plan.</p>
                  )}
                </div>
                <p className="text-sm text-ink-muted mt-4">
                  {plan.metadata.solver_type} · {plan.metadata.solver_status} ·{' '}
                  {plan.metadata.solving_time_ms}ms
                </p>
              </div>
            </details>
          );
        })}
      </div>
    </details>
  );
}

export function PlanWorkspace({
  runId,
  plans,
  recommendedPlanId,
  candidatePlanSummary = [],
  onApproved,
}: PlanWorkspaceProps) {
  const sorted = useMemo(
    () => sortPlans(plans, recommendedPlanId),
    [plans, recommendedPlanId],
  );
  const recommended = sorted[0] ?? null;
  const [pendingPlan, setPendingPlan] = useState<CandidatePlan | null>(null);
  const [confirmReject, setConfirmReject] = useState(false);
  const [actionInFlight, setActionInFlight] = useState<'approve' | 'reject' | null>(null);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    if (pendingPlan && !plans.some((plan) => plan.plan_id === pendingPlan.plan_id)) {
      setPendingPlan(null);
    }
  }, [pendingPlan, plans]);

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
    } catch (caught: unknown) {
      setError(caught instanceof Error ? caught.message : 'The decision could not be approved.');
      setActionInFlight(null);
    }
  };

  const handleReject = async () => {
    setActionInFlight('reject');
    setError(null);
    try {
      await api.approveRun(runId, { approval_status: 'REJECTED' });
      onApproved();
    } catch (caught: unknown) {
      setError(caught instanceof Error ? caught.message : 'The plans could not be rejected.');
      setActionInFlight(null);
    }
  };

  if (!recommended) {
    return (
      <div className="rounded-2xl border border-border-dim bg-deep p-8 text-center">
        <span className="mx-auto block h-6 w-6 rounded-full border-2 border-ops-cyan/30 border-t-ops-cyan animate-spin" />
        <p className="text-base font-bold text-ink-secondary mt-4">Preparing plan options…</p>
      </div>
    );
  }

  const recommendedSummary = summaryFor(recommended, candidatePlanSummary);
  const personalized = Boolean(recommendedSummary?.selected && recommendedSummary.rank > 1);
  const alternatives = sorted.filter((plan) => plan.plan_id !== recommended.plan_id);

  return (
    <div className="space-y-5 animate-fade-up">
      <header>
        <p className="text-sm font-mono font-bold uppercase tracking-[0.14em] text-ops-amber">
          Human decision
        </p>
        <h2 className="text-2xl font-extrabold tracking-[-0.04em] text-ink-primary mt-1">
          Review the recommendation.
        </h2>
      </header>

      {error && (
        <div className="rounded-xl border border-ops-rose/35 bg-ops-rose/[0.06] px-4 py-3 text-sm font-bold text-ops-rose" role="alert">
          {error}
        </div>
      )}

      {pendingPlan && (
        <section className="rounded-2xl border border-ops-amber/50 bg-ops-amber/[0.06] p-5">
          <p className="text-sm font-bold uppercase tracking-wide text-ops-amber">Final check</p>
          <div className="flex flex-col lg:flex-row lg:items-center justify-between gap-4 mt-2">
            <div>
              <h3 className="text-xl font-extrabold text-ink-primary">{profileName(pendingPlan)}</h3>
              <p className="text-sm text-ink-secondary mt-1">
                {pendingPlan.plan_id === recommended.plan_id
                  ? 'Continue with the AI recommendation.'
                  : 'Use this alternative instead of the AI recommendation.'}
              </p>
            </div>
            <div className="flex flex-wrap gap-2">
              <button
                type="button"
                disabled={actionInFlight !== null}
                onClick={() => setPendingPlan(null)}
                className="rounded-xl border border-border-base bg-abyss px-4 py-3 text-sm font-bold text-ink-secondary disabled:opacity-40 focus-ring"
              >
                Go back
              </button>
              <button
                type="button"
                disabled={actionInFlight !== null}
                onClick={() => void handleApprove()}
                className="rounded-xl bg-ops-amber px-5 py-3 text-sm font-bold text-white disabled:opacity-40 focus-ring"
              >
                {actionInFlight === 'approve' ? 'Starting execution…' : 'Confirm and execute'}
              </button>
            </div>
          </div>
        </section>
      )}

      <section className="rounded-[1.5rem] border border-ops-amber/40 bg-abyss shadow-card p-5 sm:p-6">
        <div className="flex flex-wrap items-start justify-between gap-4">
          <div>
            <div className="flex flex-wrap items-center gap-2">
              <span className="rounded-full bg-ops-amber px-3 py-1 text-sm font-bold text-white">
                {preferenceLabel(recommendedSummary)}
              </span>
              {personalized && (
                <span className="rounded-full border border-ops-violet/35 bg-ops-violet/[0.08] px-3 py-1 text-sm font-bold text-ops-violet">
                  Preference memory
                </span>
              )}
            </div>
            <h3 className="text-3xl font-extrabold tracking-[-0.045em] text-ink-primary mt-3">
              {profileName(recommended)}
            </h3>
            <p className="max-w-3xl text-base leading-relaxed text-ink-secondary mt-2">
              {preferenceReason(recommended, recommendedSummary)}
            </p>
          </div>
          <button
            type="button"
            disabled={actionInFlight !== null}
            onClick={() => setPendingPlan(recommended)}
            className="rounded-xl bg-ops-amber px-5 py-3 text-base font-bold text-white hover:bg-ops-amber-bright disabled:opacity-40 focus-ring"
          >
            Review recommendation
          </button>
        </div>

        <div className="mt-5">
          <PlanMetrics plan={recommended} summary={recommendedSummary} />
        </div>
      </section>

      {alternatives.length > 0 && (
        <section>
          <div className="flex items-center justify-between gap-3">
            <h3 className="text-xl font-extrabold text-ink-primary">Other valid options</h3>
            <span className="text-sm text-ink-muted">{alternatives.length} alternatives</span>
          </div>
          <div className="grid lg:grid-cols-3 gap-3 mt-3">
            {alternatives.map((plan) => (
              <AlternativeCard
                key={plan.plan_id}
                plan={plan}
                summary={summaryFor(plan, candidatePlanSummary)}
                busy={actionInFlight !== null}
                onSelect={setPendingPlan}
              />
            ))}
          </div>
        </section>
      )}

      <PlanEvidence plans={sorted} recommendedPlanId={recommended.plan_id} />

      <details className="rounded-2xl border border-border-dim bg-deep">
        <summary className="cursor-pointer list-none px-5 py-4 flex items-center justify-between gap-3 text-base font-bold text-ink-primary focus-ring rounded-2xl">
          <span>Reject all plans</span>
          <span className="text-ops-rose">+</span>
        </summary>
        <div className="border-t border-border-dim p-5">
          {!confirmReject ? (
            <div className="flex flex-wrap items-center justify-between gap-4">
              <p className="text-sm text-ink-secondary">
                Stop this run without changing any enterprise system.
              </p>
              <button
                type="button"
                onClick={() => setConfirmReject(true)}
                className="rounded-xl border border-ops-rose/35 bg-ops-rose/[0.06] px-4 py-2.5 text-sm font-bold text-ops-rose focus-ring"
              >
                Reject all
              </button>
            </div>
          ) : (
            <div className="flex flex-wrap items-center justify-between gap-4">
              <p className="text-sm font-bold text-ops-rose">No plan will be executed.</p>
              <div className="flex gap-2">
                <button
                  type="button"
                  onClick={() => setConfirmReject(false)}
                  className="rounded-xl border border-border-base px-4 py-2.5 text-sm font-bold text-ink-secondary"
                >
                  Go back
                </button>
                <button
                  type="button"
                  disabled={actionInFlight !== null}
                  onClick={() => void handleReject()}
                  className="rounded-xl bg-ops-rose px-4 py-2.5 text-sm font-bold text-white disabled:opacity-40"
                >
                  {actionInFlight === 'reject' ? 'Rejecting…' : 'Confirm rejection'}
                </button>
              </div>
            </div>
          )}
        </div>
      </details>
    </div>
  );
}
