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

// Sort order so the recommended plan appears first
function sortPlans(plans: CandidatePlan[], recommendedId: string | null): CandidatePlan[] {
  return [...plans].sort((a, b) => {
    if (a.plan_id === recommendedId) return -1;
    if (b.plan_id === recommendedId) return 1;
    return 0;
  });
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
      const msg = err instanceof Error ? err.message : 'Approval failed';
      setError(msg);
      setApproving(false);
    }
  };

  return (
    <div className="animate-fade-up space-y-6">
      {/* Header */}
      <div className="space-y-2">
        <div className="flex items-center gap-3">
          <span className="text-2xl">⚡</span>
          <div>
            <h2 className="text-lg font-bold text-ink-primary">Manager Approval Required</h2>
            <p className="text-xs font-mono text-ops-amber uppercase tracking-widest">
              {plans.length} candidate plans — no changes committed yet
            </p>
          </div>
        </div>
        <p className="text-sm text-ink-secondary leading-relaxed max-w-3xl">
          The AI has completed its analysis. Review all {plans.length} allocation plans below, read the explanations,
          and approve one. Only after your approval will any write operations execute in enterprise systems.
        </p>
      </div>

      {/* Decision guide strip */}
      <div className="grid grid-cols-2 md:grid-cols-4 gap-3">
        {[
          { icon: '📊', label: 'Compare metrics', tip: 'Match rate and ARR protected differ between plans' },
          { icon: '📖', label: 'Read explanations', tip: 'Each plan has a full Markdown narrative from the AI' },
          { icon: '⭐', label: 'Check recommendation', tip: 'Gold border = system-recommended based on your goal' },
          { icon: '✅', label: 'Approve one plan', tip: 'You can only approve one. This triggers SAGA execution' },
        ].map(({ icon, label, tip }) => (
          <div key={label} className="bg-abyss border border-border-dim rounded-lg p-3 space-y-1">
            <p className="text-base">{icon}</p>
            <p className="text-xs font-semibold text-ink-primary">{label}</p>
            <p className="text-xs text-ink-muted leading-relaxed">{tip}</p>
          </div>
        ))}
      </div>

      {/* Error */}
      {error && (
        <div className="border border-ops-rose/40 bg-ops-rose/8 rounded-lg px-4 py-3 text-sm text-ops-rose animate-fade-up">
          ✗ {error}
        </div>
      )}

      {/* Plan cards grid */}
      {sorted.length > 0 ? (
        <div className="grid grid-cols-1 md:grid-cols-2 xl:grid-cols-4 gap-6 items-start">
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
      ) : (
        <div className="border border-border-dim rounded-xl p-12 text-center space-y-3">
          <p className="text-4xl">⏳</p>
          <p className="text-sm text-ink-secondary">Candidate plans are being generated…</p>
          <p className="text-xs text-ink-muted font-mono">CP-SAT solver is running optimisation profiles</p>
        </div>
      )}
    </div>
  );
}
