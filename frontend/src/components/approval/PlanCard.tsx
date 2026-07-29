import { useState } from 'react';
import Markdown from 'react-markdown';
import type { CandidatePlan } from '../../types/api';

interface PlanCardProps {
  plan: CandidatePlan;
  isRecommended: boolean;
  onSelect: (plan: CandidatePlan) => void;
  busy: boolean;
}

const PROFILE_ACCENTS: Record<string, { border: string; badge: string; glow: string }> = {
  'Balanced':       { border: 'border-ops-cyan/40',    badge: 'text-ops-cyan bg-ops-cyan/10',      glow: 'hover:shadow-cyan-glow' },
  'SLA-First':      { border: 'border-ops-amber/40',   badge: 'text-ops-amber bg-ops-amber/10',     glow: 'hover:shadow-amber-glow' },
  'Revenue-First':  { border: 'border-ops-emerald/40', badge: 'text-ops-emerald bg-ops-emerald/10', glow: 'hover:glow-emerald' },
  'Fairness-First': { border: 'border-ops-violet/40',  badge: 'text-ops-violet bg-ops-violet/10',   glow: 'hover:shadow-card' },
};

const SOLVER_STATUS_COLOR: Record<string, string> = {
  OPTIMAL:    'text-ops-emerald',
  FEASIBLE:   'text-ops-amber',
  TIME_LIMIT: 'text-ops-orange',
};

function MetricRow({ label, value, unit = '' }: { label: string; value: string | number; unit?: string }) {
  return (
    <div className="flex items-center justify-between py-1.5 border-b border-border-dim last:border-0">
      <span className="text-xs text-ink-muted font-mono">{label}</span>
      <span className="text-xs font-mono font-semibold text-ink-primary">
        {value}{unit}
      </span>
    </div>
  );
}

export function PlanCard({ plan, isRecommended, onSelect, busy }: PlanCardProps) {
  const [showExplanation, setShowExplanation] = useState(false);
  const [showMetadata, setShowMetadata] = useState(false);

  const profile = plan.profile_name ?? plan.profile;
  const accent = PROFILE_ACCENTS[profile] ?? PROFILE_ACCENTS['Balanced'];
  const matchRatePct = typeof plan.metrics.match_rate === 'number'
    ? `${(plan.metrics.match_rate <= 1
      ? plan.metrics.match_rate * 100
      : plan.metrics.match_rate
    ).toFixed(1)}%`
    : plan.metrics.match_rate;
  const arrProtected = typeof plan.metrics.arr_protected === 'number'
    ? new Intl.NumberFormat('en-US', {
        style: 'currency',
        currency: 'USD',
        notation: plan.metrics.arr_protected >= 1_000_000 ? 'compact' : 'standard',
        maximumFractionDigits: 0,
      }).format(plan.metrics.arr_protected)
    : plan.metrics.arr_protected;

  return (
    <div
      className={`relative flex flex-col bg-deep rounded-xl border transition-all duration-300
        ${isRecommended
          ? 'border-ops-amber shadow-amber-glow ring-1 ring-ops-amber/30'
          : `${accent.border} ${accent.glow}`
        }`}
    >
      {/* Recommended badge */}
      {isRecommended && (
        <div className="absolute -top-3 left-1/2 -translate-x-1/2 z-10">
          <span className="bg-ops-amber text-void text-xs font-bold px-3 py-1 rounded-full uppercase tracking-widest whitespace-nowrap">
            Recommended for this goal
          </span>
        </div>
      )}

      {/* Header */}
      <div className={`px-5 pt-6 pb-4 border-b border-border-dim ${isRecommended ? 'pt-8' : ''}`}>
        <div className="flex items-center justify-between mb-1">
          <span className={`text-xs font-mono font-semibold px-2 py-0.5 rounded uppercase tracking-wider ${accent.badge}`}>
            {profile}
          </span>
          <span className="text-xs font-mono text-ink-muted">{plan.plan_id}</span>
        </div>
        <p className="text-sm text-ink-secondary leading-relaxed mt-2">{plan.description}</p>
      </div>

      {/* Core metrics */}
      <div className="px-5 py-4 border-b border-border-dim">
        <p className="text-xs font-mono text-ink-muted uppercase tracking-widest mb-3">Key Metrics</p>
        <MetricRow label="Match Rate"        value={matchRatePct} />
        <MetricRow label="Assigned"          value={plan.metrics.assigned_count ?? '—'} />
        <MetricRow label="Unassigned"        value={plan.metrics.unassigned_count ?? '—'} />
        <MetricRow label="ARR Protected"     value={arrProtected} />
        <MetricRow label="Objective Score"   value={plan.objective_value.toFixed(0)} />
      </div>

      {/* Explanation toggle */}
      <div className="px-5 py-3 border-b border-border-dim">
        <button
          onClick={() => setShowExplanation(!showExplanation)}
          className="w-full flex items-center justify-between text-xs font-mono text-ink-secondary hover:text-ink-primary transition-colors"
        >
          <span className="uppercase tracking-widest">Plan reasoning</span>
          <span className={`transition-transform duration-200 ${showExplanation ? 'rotate-180' : ''}`}>▼</span>
        </button>
        {showExplanation && (
          <div className="mt-3 markdown-body max-h-48 overflow-y-auto pr-1 animate-fade-up">
            <Markdown>{plan.explanation}</Markdown>
            <p className="text-[9px] text-ink-ghost mt-3">
              This explanation is supplied by the backend and may come from configured AI assistance or deterministic rules.
            </p>
          </div>
        )}
      </div>

      {/* Technical metadata toggle */}
      <div className="px-5 py-3 border-b border-border-dim">
        <button
          onClick={() => setShowMetadata(!showMetadata)}
          className="w-full flex items-center justify-between text-xs font-mono text-ink-secondary hover:text-ink-primary transition-colors"
        >
          <span className="uppercase tracking-widest">Technical Details</span>
          <span className={`transition-transform duration-200 ${showMetadata ? 'rotate-180' : ''}`}>▼</span>
        </button>
        {showMetadata && (
          <div className="mt-3 space-y-1.5 animate-fade-up">
            <div className="flex justify-between text-xs font-mono">
              <span className="text-ink-muted">Solver</span>
              <span className="text-ink-secondary">{plan.metadata.solver_type}</span>
            </div>
            <div className="flex justify-between text-xs font-mono">
              <span className="text-ink-muted">Solve Time</span>
              <span className="text-ink-secondary">{plan.metadata.solving_time_ms}ms</span>
            </div>
            <div className="flex justify-between text-xs font-mono">
              <span className="text-ink-muted">Status</span>
              <span className={SOLVER_STATUS_COLOR[plan.metadata.solver_status] ?? 'text-ink-secondary'}>
                {plan.metadata.solver_status}
              </span>
            </div>
            <div className="flex justify-between text-xs font-mono">
              <span className="text-ink-muted">Fallback</span>
              <span className="text-ink-secondary">{plan.metadata.fallback_status ? 'Yes' : 'No'}</span>
            </div>
            <p className="text-xs text-ink-ghost mt-2 leading-relaxed">
              Solver metadata is read-only diagnostic information — it is never modified by the frontend.
            </p>
          </div>
        )}
      </div>

      {/* Approve button */}
      <div className="px-5 py-4 mt-auto">
        <button
          onClick={() => onSelect(plan)}
          disabled={busy}
          className={`w-full py-3 rounded-lg font-bold text-sm tracking-widest uppercase transition-all duration-200
            disabled:opacity-40 disabled:cursor-not-allowed
            ${isRecommended
              ? 'bg-ops-amber text-void hover:bg-ops-amber-bright glow-amber'
              : 'bg-surface border border-border-base text-ink-primary hover:border-ops-amber hover:text-ops-amber'
            }`}
        >
          {busy ? (
            <span className="flex items-center justify-center gap-2">
              <span className="w-4 h-4 border-2 border-current/30 border-t-current rounded-full animate-spin" />
              Approving…
            </span>
          ) : (
            isRecommended ? 'Review recommended plan' : `Review ${profile} override`
          )}
        </button>
      </div>
    </div>
  );
}
