import { useMemo, useState } from 'react';
import { api } from '../../api/client';
import type {
  AllocationRecord,
  CandidatePlan,
  DemoPortfolio,
  DemoSpecialist,
} from '../../types/api';

interface ManualAssignmentPanelProps {
  runId: string;
  plan: CandidatePlan;
  onApproved: () => void;
}

function allocationsFor(plan: CandidatePlan): AllocationRecord[] {
  return plan.assignments.length ? plan.assignments : plan.allocations;
}

function canHandle(
  worker: DemoSpecialist,
  requiredSkills: string[],
): boolean {
  if (worker.availability === false || worker.operationally_available === false) return false;
  if ((worker.available_capacity ?? 0) < 1) return false;
  if (requiredSkills.length === 0) return true;
  const skills = new Set(worker.skills.map((skill) => skill.toLowerCase()));
  return requiredSkills.some((skill) => skills.has(skill.toLowerCase()));
}

export function ManualAssignmentPanel({
  runId,
  plan,
  onApproved,
}: ManualAssignmentPanelProps) {
  const baseAllocations = useMemo(() => allocationsFor(plan), [plan]);
  const [portfolio, setPortfolio] = useState<DemoPortfolio | null>(null);
  const [assignments, setAssignments] = useState<Record<string, string>>(() => (
    Object.fromEntries(baseAllocations.map((item) => [item.incident_id, item.specialist_id]))
  ));
  const [reason, setReason] = useState('');
  const [loading, setLoading] = useState(false);
  const [submitting, setSubmitting] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const loadLiveData = async () => {
    if (portfolio || loading) return;
    setLoading(true);
    setError(null);
    try {
      setPortfolio(await api.getDemoPortfolio());
    } catch (caught: unknown) {
      setError(caught instanceof Error ? caught.message : 'Live worker data could not be loaded.');
    } finally {
      setLoading(false);
    }
  };

  const capacityError = useMemo(() => {
    if (!portfolio) return null;
    const counts = Object.values(assignments).reduce<Record<string, number>>((result, specialistId) => {
      result[specialistId] = (result[specialistId] ?? 0) + 1;
      return result;
    }, {});
    for (const [specialistId, assignedCount] of Object.entries(counts)) {
      const worker = portfolio.specialists.find((item) => item.specialist_id === specialistId);
      if (!worker || assignedCount > (worker.available_capacity ?? 0)) {
        return `${worker?.specialist_name ?? specialistId} does not have capacity for ${assignedCount} new assignments.`;
      }
    }
    return null;
  }, [assignments, portfolio]);

  const executeManualPlan = async () => {
    if (!portfolio || capacityError) return;
    if (baseAllocations.some((item) => !assignments[item.incident_id])) {
      setError('Choose one worker for every incident.');
      return;
    }

    const manualAllocations = baseAllocations.map((allocation) => {
      const incident = portfolio.incidents.find((item) => item.incident_id === allocation.incident_id);
      const worker = portfolio.specialists.find(
        (item) => item.specialist_id === assignments[allocation.incident_id],
      );
      const workerSkills = new Set((worker?.skills ?? []).map((skill) => skill.toLowerCase()));
      return {
        ...allocation,
        specialist_id: assignments[allocation.incident_id],
        matched_skills: (incident?.required_skills ?? []).filter(
          (skill) => workerSkills.has(skill.toLowerCase()),
        ),
      };
    });

    setSubmitting(true);
    setError(null);
    try {
      await api.approveRun(runId, {
        approval_status: 'APPROVED',
        recommended_plan: {
          ...plan,
          plan_id: `MANUAL-${runId}`,
          profile_id: 'MANUAL',
          profile_name: 'Manual assignment',
          profile: 'Manual assignment',
          description: 'Manager-selected incident ownership.',
          explanation: reason.trim() || 'Manager selected each worker manually.',
          allocations: manualAllocations,
          assignments: manualAllocations,
        },
        decision_reason: reason.trim() || 'Manager selected each worker manually.',
        decision_source: 'MANUAL_PLAN',
      });
      onApproved();
    } catch (caught: unknown) {
      setError(caught instanceof Error ? caught.message : 'The manual plan could not be executed.');
      setSubmitting(false);
    }
  };

  return (
    <details
      className="group rounded-2xl border border-border-dim bg-deep"
      onToggle={(event) => {
        if (event.currentTarget.open) void loadLiveData();
      }}
    >
      <summary className="flex min-h-12 cursor-pointer list-none items-center justify-between gap-3 rounded-2xl px-5 py-4 text-base font-bold text-ink-primary focus-ring">
        <span>Assign workers manually</span>
        <span className="text-ops-cyan transition-transform group-open:rotate-45">+</span>
      </summary>

      <div className="border-t border-border-dim p-5">
        <p className="text-sm text-ink-secondary">
          Only live, available workers with matching skills and free capacity are shown.
        </p>

        {loading && <p className="mt-4 text-sm font-bold text-ink-muted">Loading live workers…</p>}
        {error && <p className="mt-4 text-sm font-bold text-ops-rose" role="alert">{error}</p>}

        {portfolio && (
          <>
            <div className="mt-4 space-y-3">
              {baseAllocations.map((allocation) => {
                const incident = portfolio.incidents.find(
                  (item) => item.incident_id === allocation.incident_id,
                );
                const eligible = portfolio.specialists.filter(
                  (worker) => canHandle(worker, incident?.required_skills ?? []),
                );
                return (
                  <label
                    key={allocation.incident_id}
                    className="grid gap-3 rounded-xl border border-border-dim bg-abyss p-4 sm:grid-cols-[minmax(0,1fr)_minmax(220px,0.8fr)] sm:items-center"
                  >
                    <span>
                      <span className="block text-base font-bold text-ink-primary">
                        {incident?.title ?? allocation.incident_id}
                      </span>
                      <span className="mt-1 block text-sm text-ink-muted">
                        {(incident?.required_skills ?? []).join(' · ') || 'No required skill'}
                      </span>
                    </span>
                    <select
                      value={assignments[allocation.incident_id] ?? ''}
                      onChange={(event) => setAssignments((current) => ({
                        ...current,
                        [allocation.incident_id]: event.target.value,
                      }))}
                      className="min-h-11 w-full rounded-xl border border-border-base bg-deep px-3 py-2 text-base font-bold text-ink-primary focus-ring"
                    >
                      <option value="">Choose worker</option>
                      {eligible.map((worker) => (
                        <option key={worker.specialist_id} value={worker.specialist_id}>
                          {worker.specialist_name} · {worker.available_capacity} free · {Math.round(worker.effectiveness_score ?? 0)}%
                        </option>
                      ))}
                    </select>
                  </label>
                );
              })}
            </div>

            <label className="mt-4 block">
              <span className="text-sm font-bold text-ink-secondary">Reason for manual assignment</span>
              <textarea
                value={reason}
                maxLength={1000}
                rows={2}
                onChange={(event) => setReason(event.target.value)}
                placeholder="Optional context saved to decision memory"
                className="mt-2 w-full resize-y rounded-xl border border-border-base bg-abyss px-4 py-3 text-base text-ink-primary placeholder:text-ink-muted focus-ring"
              />
            </label>

            {capacityError && <p className="mt-3 text-sm font-bold text-ops-rose">{capacityError}</p>}
            <div className="mt-4 flex justify-end">
              <button
                type="button"
                disabled={submitting || Boolean(capacityError)}
                onClick={() => void executeManualPlan()}
                className="min-h-11 rounded-xl bg-ink-primary px-5 py-3 text-sm font-bold text-white hover:bg-ops-cyan disabled:opacity-40 focus-ring"
              >
                {submitting ? 'Executing manual plan…' : 'Execute manual plan'}
              </button>
            </div>
          </>
        )}
      </div>
    </details>
  );
}
