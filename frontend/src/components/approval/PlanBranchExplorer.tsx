import { useEffect, useMemo, useState } from 'react';
import type { CandidatePlan } from '../../types/api';

interface PlanBranchExplorerProps {
  plans: CandidatePlan[];
  recommendedPlanId: string | null;
  busy: boolean;
  onReview: (plan: CandidatePlan) => void;
}

interface Consequence {
  label: string;
  selectedValue: string;
  baselineValue: string;
  delta: number | null;
  direction: 'higher' | 'lower';
  tone: 'cyan' | 'emerald' | 'amber' | 'rose' | 'violet';
}

const PROFILE_STYLE: Record<string, {
  short: string;
  border: string;
  text: string;
  background: string;
  marker: string;
}> = {
  Balanced: {
    short: 'BAL',
    border: 'border-ops-cyan/40',
    text: 'text-ops-cyan',
    background: 'bg-ops-cyan/[0.065]',
    marker: 'bg-ops-cyan',
  },
  'SLA-First': {
    short: 'SLA',
    border: 'border-ops-rose/40',
    text: 'text-ops-rose',
    background: 'bg-ops-rose/[0.065]',
    marker: 'bg-ops-rose',
  },
  'Revenue-First': {
    short: 'ARR',
    border: 'border-ops-emerald/40',
    text: 'text-ops-emerald',
    background: 'bg-ops-emerald/[0.065]',
    marker: 'bg-ops-emerald',
  },
  'Revenue First': {
    short: 'ARR',
    border: 'border-ops-emerald/40',
    text: 'text-ops-emerald',
    background: 'bg-ops-emerald/[0.065]',
    marker: 'bg-ops-emerald',
  },
  'Fairness-First': {
    short: 'FAIR',
    border: 'border-ops-violet/40',
    text: 'text-ops-violet',
    background: 'bg-ops-violet/[0.065]',
    marker: 'bg-ops-violet',
  },
  'Fairness First': {
    short: 'FAIR',
    border: 'border-ops-violet/40',
    text: 'text-ops-violet',
    background: 'bg-ops-violet/[0.065]',
    marker: 'bg-ops-violet',
  },
};

const TONE_TEXT = {
  cyan: 'text-ops-cyan',
  emerald: 'text-ops-emerald',
  amber: 'text-ops-amber',
  rose: 'text-ops-rose',
  violet: 'text-ops-violet',
};

function profileName(plan: CandidatePlan): string {
  return plan.profile_name ?? plan.profile;
}

function numericMetric(plan: CandidatePlan, key: string): number | null {
  const value = plan.metrics[key];
  return typeof value === 'number' && Number.isFinite(value) ? value : null;
}

function formatPercent(value: number): string {
  return `${(value <= 1 ? value * 100 : value).toFixed(0)}%`;
}

function formatMoney(value: number): string {
  return new Intl.NumberFormat('en-US', {
    style: 'currency',
    currency: 'USD',
    notation: 'compact',
    maximumFractionDigits: 1,
  }).format(value);
}

function formatCount(value: number): string {
  return Math.round(value).toString();
}

function allocationKey(plan: CandidatePlan): Set<string> {
  const allocations = plan.assignments.length > 0 ? plan.assignments : plan.allocations;
  return new Set(
    allocations.map((allocation) => `${allocation.incident_id}:${allocation.specialist_id}`),
  );
}

function changedAllocations(selected: CandidatePlan, baseline: CandidatePlan): number {
  const selectedKeys = allocationKey(selected);
  const baselineKeys = allocationKey(baseline);
  return new Set([
    ...Array.from(selectedKeys).filter((key) => !baselineKeys.has(key)),
    ...Array.from(baselineKeys).filter((key) => !selectedKeys.has(key)),
  ]).size;
}

function consequence(
  selected: CandidatePlan,
  baseline: CandidatePlan,
  config: {
    key: string;
    label: string;
    direction: Consequence['direction'];
    tone: Consequence['tone'];
    format: (value: number) => string;
  },
): Consequence | null {
  const selectedNumber = numericMetric(selected, config.key);
  const baselineNumber = numericMetric(baseline, config.key);
  if (selectedNumber === null && baselineNumber === null) return null;

  return {
    label: config.label,
    selectedValue: selectedNumber === null ? '—' : config.format(selectedNumber),
    baselineValue: baselineNumber === null ? '—' : config.format(baselineNumber),
    delta: selectedNumber !== null && baselineNumber !== null
      ? selectedNumber - baselineNumber
      : null,
    direction: config.direction,
    tone: config.tone,
  };
}

function deltaLabel(item: Consequence): { label: string; positive: boolean | null } {
  if (item.delta === null || Math.abs(item.delta) < 0.0001) {
    return { label: 'same', positive: null };
  }
  const positive = item.direction === 'higher' ? item.delta > 0 : item.delta < 0;
  return {
    label: `${item.delta > 0 ? '+' : ''}${Number.isInteger(item.delta) ? item.delta : item.delta.toFixed(1)}`,
    positive,
  };
}

export function PlanBranchExplorer({
  plans,
  recommendedPlanId,
  busy,
  onReview,
}: PlanBranchExplorerProps) {
  const recommended = plans.find((plan) => plan.plan_id === recommendedPlanId) ?? plans[0];
  const [selectedPlanId, setSelectedPlanId] = useState(recommended?.plan_id ?? '');

  useEffect(() => {
    if (!plans.some((plan) => plan.plan_id === selectedPlanId)) {
      setSelectedPlanId(recommended?.plan_id ?? plans[0]?.plan_id ?? '');
    }
  }, [plans, recommended?.plan_id, selectedPlanId]);

  const selected = plans.find((plan) => plan.plan_id === selectedPlanId) ?? recommended;
  const consequences = useMemo(() => {
    if (!selected || !recommended) return [];
    const configs = [
      {
        key: 'assigned_count',
        label: 'Incidents covered',
        direction: 'higher' as const,
        tone: 'cyan' as const,
        format: formatCount,
      },
      {
        key: 'unassigned_count',
        label: 'Work left waiting',
        direction: 'lower' as const,
        tone: 'amber' as const,
        format: formatCount,
      },
      {
        key: 'arr_protected',
        label: 'ARR protected',
        direction: 'higher' as const,
        tone: 'emerald' as const,
        format: formatMoney,
      },
      {
        key: 'sla_breaches_avoided',
        label: 'SLA breaches avoided',
        direction: 'higher' as const,
        tone: 'rose' as const,
        format: formatCount,
      },
      {
        key: 'fairness_score',
        label: 'Fairness',
        direction: 'higher' as const,
        tone: 'violet' as const,
        format: formatPercent,
      },
      {
        key: 'maximum_specialist_utilisation',
        label: 'Peak utilisation',
        direction: 'lower' as const,
        tone: 'amber' as const,
        format: formatPercent,
      },
    ];
    return configs
      .map((config) => consequence(selected, recommended, config))
      .filter((item): item is Consequence => item !== null);
  }, [recommended, selected]);

  if (!selected || !recommended) return null;

  const selectedProfile = profileName(selected);
  const recommendedProfile = profileName(recommended);
  const selectedStyle = PROFILE_STYLE[selectedProfile] ?? PROFILE_STYLE.Balanced;
  const isRecommended = selected.plan_id === recommended.plan_id;
  const feasible = selected.feasible
    ?? selected.metadata.feasibility
    ?? selected.metadata.solver_status !== 'INFEASIBLE';
  const changedAssignmentCount = changedAllocations(selected, recommended);
  const objectiveMaximum = Math.max(...plans.map((plan) => plan.objective_value), 1);
  const objectiveWidth = Math.max(4, (selected.objective_value / objectiveMaximum) * 100);

  return (
    <section className="rounded-[1.5rem] border border-border-base bg-abyss overflow-hidden shadow-card" aria-labelledby="branch-explorer-title">
      <div className="px-5 sm:px-6 py-5 border-b border-border-dim bg-deep/55">
        <div className="flex flex-wrap items-start justify-between gap-4">
          <div>
            <p className="text-[8px] font-mono font-semibold uppercase tracking-[0.17em] text-ops-cyan">
              What-if branch explorer
            </p>
            <h3 id="branch-explorer-title" className="text-lg font-extrabold tracking-[-0.035em] text-ink-primary mt-1">
              Preview another decision.
            </h3>
          </div>
          <span className="rounded-full border border-ops-emerald/30 bg-ops-emerald/5 px-3 py-1.5 text-[8px] font-mono font-semibold uppercase text-ops-emerald">
            Preview only · no execution
          </span>
        </div>

        <div className="relative mt-6">
          <div className="absolute left-[8%] right-[8%] top-7 h-px bg-border-base" />
          <div className="grid grid-cols-2 sm:grid-cols-4 gap-3 relative z-10">
            {plans.map((plan) => {
              const profile = profileName(plan);
              const style = PROFILE_STYLE[profile] ?? PROFILE_STYLE.Balanced;
              const active = plan.plan_id === selected.plan_id;
              const planRecommended = plan.plan_id === recommended.plan_id;
              return (
                <button
                  key={plan.plan_id}
                  type="button"
                  onClick={() => setSelectedPlanId(plan.plan_id)}
                  aria-pressed={active}
                  className={`rounded-2xl border p-3 text-left transition-all focus-ring ${
                    active
                      ? `${style.border} ${style.background} shadow-card -translate-y-0.5`
                      : 'border-border-dim bg-abyss hover:border-border-base'
                  }`}
                >
                  <div className="flex items-center justify-between gap-2">
                    <span className={`w-11 h-11 rounded-full border-2 flex items-center justify-center text-[9px] font-mono font-bold ${
                      active ? `${style.border} ${style.text} ${style.background}` : 'border-border-base bg-deep text-ink-muted'
                    }`}>
                      {style.short}
                    </span>
                    {planRecommended && (
                      <span className="rounded-full bg-ops-amber px-2 py-1 text-[7px] font-mono font-bold uppercase text-white">
                        Core
                      </span>
                    )}
                  </div>
                  <p className={`text-[10px] font-extrabold mt-2 ${active ? style.text : 'text-ink-secondary'}`}>
                    {profile}
                  </p>
                  <p className="text-[8px] font-mono text-ink-muted mt-0.5">
                    score {plan.objective_value.toFixed(0)}
                  </p>
                </button>
              );
            })}
          </div>
        </div>
      </div>

      <div className="p-5 sm:p-6">
        <div className="flex flex-col lg:flex-row lg:items-start justify-between gap-5">
          <div>
            <div className="flex flex-wrap items-center gap-2">
              <span className={`w-2 h-2 rounded-full ${selectedStyle.marker}`} />
              <h4 className="text-base font-extrabold text-ink-primary">{selectedProfile}</h4>
              {!isRecommended && (
                <span className="rounded-full bg-ops-violet/10 px-2 py-1 text-[7px] font-mono uppercase text-ops-violet">
                  compared with {recommendedProfile}
                </span>
              )}
            </div>
            <p className="max-w-2xl text-[10px] leading-relaxed text-ink-muted mt-2">
              {selected.description}
            </p>
          </div>
          <div className="flex items-center gap-3">
            <div className="text-right">
              <p className={`text-[9px] font-mono font-bold ${feasible ? 'text-ops-emerald' : 'text-ops-rose'}`}>
                {feasible ? 'FEASIBLE' : 'NOT FEASIBLE'}
              </p>
              <p className="text-[8px] text-ink-muted mt-0.5">
                {changedAssignmentCount} assignment difference{changedAssignmentCount === 1 ? '' : 's'}
              </p>
            </div>
            <span className={`w-10 h-10 rounded-full border flex items-center justify-center ${
              feasible
                ? 'border-ops-emerald/30 bg-ops-emerald/10 text-ops-emerald'
                : 'border-ops-rose/30 bg-ops-rose/10 text-ops-rose'
            }`}>
              {feasible ? '✓' : '!'}
            </span>
          </div>
        </div>

        <div className="mt-5">
          <div className="flex items-center justify-between text-[8px] font-mono uppercase text-ink-muted">
            <span>Objective strength</span>
            <span className={selectedStyle.text}>{selected.objective_value.toFixed(1)}</span>
          </div>
          <div className="h-1.5 rounded-full bg-surface overflow-hidden mt-2">
            <div
              className={`h-full rounded-full ${selectedStyle.marker} transition-[width] duration-500`}
              style={{ width: `${objectiveWidth}%` }}
            />
          </div>
        </div>

        <div className="grid sm:grid-cols-2 xl:grid-cols-3 gap-2 mt-5">
          {consequences.map((item) => {
            const change = deltaLabel(item);
            return (
              <article key={item.label} className="rounded-xl border border-border-dim bg-deep/55 p-3.5">
                <div className="flex items-center justify-between gap-2">
                  <p className="text-[8px] font-mono uppercase tracking-[0.11em] text-ink-muted">
                    {item.label}
                  </p>
                  <span className={`text-[8px] font-mono font-bold ${
                    change.positive === true
                      ? 'text-ops-emerald'
                      : change.positive === false
                        ? 'text-ops-rose'
                        : 'text-ink-muted'
                  }`}>
                    {change.label}
                  </span>
                </div>
                <div className="flex items-end justify-between gap-3 mt-2">
                  <span className={`text-xl font-extrabold tracking-[-0.04em] ${TONE_TEXT[item.tone]}`}>
                    {item.selectedValue}
                  </span>
                  {!isRecommended && (
                    <span className="text-[8px] text-ink-muted">
                      Core {item.baselineValue}
                    </span>
                  )}
                </div>
              </article>
            );
          })}
        </div>

        <details className="group mt-4">
          <summary className="cursor-pointer list-none rounded-xl border border-border-dim bg-deep/55 px-4 py-3 flex items-center justify-between gap-3 text-[9px] font-semibold text-ink-secondary hover:border-border-base focus-ring">
            <span>Why this branch behaves differently</span>
            <span className={`group-open:rotate-45 transition-transform ${selectedStyle.text}`}>+</span>
          </summary>
          <div className="rounded-xl border border-border-dim bg-deep/45 p-4 mt-2">
            <p className="text-[10px] leading-relaxed text-ink-secondary whitespace-pre-wrap">
              {selected.explanation}
            </p>
            <div className="flex flex-wrap gap-1.5 mt-3">
              {Object.entries(selected.objective_weights ?? {}).map(([key, value]) => (
                <span key={key} className="rounded-full border border-border-dim bg-abyss px-2.5 py-1 text-[8px] font-mono text-ink-muted">
                  {key} {value}
                </span>
              ))}
            </div>
          </div>
        </details>

        <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-3 mt-5 pt-5 border-t border-border-dim">
          <p className="text-[9px] leading-relaxed text-ink-muted">
            Selecting a branch changes only this preview. Confirmation remains a separate step.
          </p>
          <button
            type="button"
            onClick={() => onReview(selected)}
            disabled={busy || !feasible}
            className={`shrink-0 rounded-xl px-5 py-3 text-[10px] font-bold focus-ring disabled:opacity-40 disabled:cursor-not-allowed ${
              isRecommended
                ? 'bg-ops-amber text-white hover:bg-ops-amber-bright'
                : 'border border-ops-violet/35 bg-ops-violet/10 text-ops-violet hover:bg-ops-violet/15'
            }`}
          >
            {isRecommended ? 'Review recommended branch' : `Review ${selectedProfile} override`}
          </button>
        </div>
      </div>
    </section>
  );
}
