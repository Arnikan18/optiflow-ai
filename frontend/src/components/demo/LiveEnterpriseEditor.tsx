import { useEffect, useMemo, useState } from 'react';
import type {
  DemoIncident,
  DemoPortfolio,
  DemoSpecialist,
  EnterpriseEventType,
} from '../../types/api';

type EditorView = 'PROBLEM' | 'WORKER';
type ProblemChange = 'PRIORITY' | 'SLA' | 'EFFORT' | 'RESOLVE';
type WorkerChange = 'AVAILABILITY' | 'CAPACITY';

export interface EnterpriseChange {
  eventType: EnterpriseEventType;
  label: string;
  description: string;
  payload: Record<string, unknown>;
}

interface LiveEnterpriseEditorProps {
  portfolio: DemoPortfolio | null;
  disabled: boolean;
  busy: boolean;
  onApply: (change: EnterpriseChange) => Promise<void>;
}

const ACTIVE_STATUSES = new Set(['OPEN', 'IN_PROGRESS', 'PENDING']);

function activeProblems(portfolio: DemoPortfolio | null): DemoIncident[] {
  return (portfolio?.incidents ?? []).filter((incident) => (
    ACTIVE_STATUSES.has(incident.status?.toUpperCase() ?? '')
  ));
}

function workerLoad(worker: DemoSpecialist): string {
  const current = worker.current_workload ?? 0;
  const capacity = worker.capacity ?? 0;
  return `${current}/${capacity}`;
}

function minutesFromNow(minutes: number): string {
  return new Date(Date.now() + minutes * 60_000).toISOString();
}

export function LiveEnterpriseEditor({
  portfolio,
  disabled,
  busy,
  onApply,
}: LiveEnterpriseEditorProps) {
  const problems = useMemo(() => activeProblems(portfolio), [portfolio]);
  const workers = portfolio?.specialists ?? [];
  const [view, setView] = useState<EditorView>('PROBLEM');
  const [problemId, setProblemId] = useState('');
  const [workerId, setWorkerId] = useState('');
  const [problemChange, setProblemChange] = useState<ProblemChange>('PRIORITY');
  const [workerChange, setWorkerChange] = useState<WorkerChange>('AVAILABILITY');
  const [slaMinutes, setSlaMinutes] = useState(45);
  const [effortMinutes, setEffortMinutes] = useState(120);
  const [workerCapacity, setWorkerCapacity] = useState(1);
  const [workerWorkload, setWorkerWorkload] = useState(0);

  useEffect(() => {
    if (!problems.some((problem) => problem.incident_id === problemId)) {
      setProblemId(problems[0]?.incident_id ?? '');
    }
  }, [problemId, problems]);

  useEffect(() => {
    if (!workers.some((worker) => worker.specialist_id === workerId)) {
      setWorkerId(workers[0]?.specialist_id ?? '');
    }
  }, [workerId, workers]);

  const problem = problems.find((item) => item.incident_id === problemId) ?? null;
  const worker = workers.find((item) => item.specialist_id === workerId) ?? null;

  useEffect(() => {
    if (problem?.estimated_effort_minutes) {
      setEffortMinutes(problem.estimated_effort_minutes);
    }
  }, [problem?.estimated_effort_minutes, problem?.incident_id]);

  useEffect(() => {
    if (!worker) return;
    setWorkerCapacity(worker.capacity ?? 1);
    setWorkerWorkload(worker.current_workload ?? 0);
  }, [worker?.capacity, worker?.current_workload, worker?.specialist_id]);

  const applyProblemChange = async () => {
    if (!problem) return;

    if (problemChange === 'PRIORITY') {
      await onApply({
        eventType: 'ESCALATE_PRIORITY',
        label: `${problem.incident_id} made critical`,
        description: `Raise ${problem.incident_id} to critical priority.`,
        payload: { incident_id: problem.incident_id, new_priority: 'CRITICAL' },
      });
      return;
    }

    if (problemChange === 'SLA') {
      await onApply({
        eventType: 'CHANGE_SLA',
        label: `${problem.incident_id} SLA changed`,
        description: `Move ${problem.incident_id} SLA to ${slaMinutes} minutes from now.`,
        payload: {
          incident_id: problem.incident_id,
          sla_deadline: minutesFromNow(slaMinutes),
        },
      });
      return;
    }

    if (problemChange === 'EFFORT') {
      await onApply({
        eventType: 'CHANGE_ESTIMATED_EFFORT',
        label: `${problem.incident_id} effort changed`,
        description: `Set ${problem.incident_id} estimated effort to ${effortMinutes} minutes.`,
        payload: {
          incident_id: problem.incident_id,
          estimated_effort_minutes: effortMinutes,
        },
      });
      return;
    }

    await onApply({
      eventType: 'RESOLVE_TICKET',
      label: `${problem.incident_id} resolved`,
      description: `Resolve ${problem.incident_id} and release its workload.`,
      payload: {
        incident_id: problem.incident_id,
        resolved_at: new Date().toISOString(),
        resolution_note: 'Resolved from the live demo control room.',
      },
    });
  };

  const applyWorkerChange = async () => {
    if (!worker) return;
    if (workerChange === 'CAPACITY') {
      await onApply({
        eventType: 'CHANGE_WORKER_CAPACITY',
        label: `${worker.specialist_name} capacity changed`,
        description: `Set ${worker.specialist_name} to ${workerWorkload} active assignments with capacity ${workerCapacity}.`,
        payload: {
          specialist_id: worker.specialist_id,
          capacity: workerCapacity,
          current_workload: workerWorkload,
          reason: 'Judge changed worker capacity in the live demo.',
        },
      });
      return;
    }

    const returning = worker.availability === false;
    await onApply({
      eventType: returning ? 'ENGINEER_RETURNED' : 'ENGINEER_ON_LEAVE',
      label: `${worker.specialist_name} ${returning ? 'returned' : 'became unavailable'}`,
      description: `${returning ? 'Return' : 'Remove'} ${worker.specialist_name} ${
        returning ? 'to' : 'from'
      } the available team.`,
      payload: {
        specialist_id: worker.specialist_id,
        reason: 'Judge changed worker availability in the live demo.',
        effective_at: new Date().toISOString(),
      },
    });
  };

  const problemPriorityDisabled = problem?.severity?.toUpperCase() === 'CRITICAL';
  const workerCapacityInvalid = workerCapacity < 1 || workerWorkload > workerCapacity;
  const actionDisabled = disabled || busy || (
    view === 'PROBLEM'
      ? !problem || (problemChange === 'PRIORITY' && problemPriorityDisabled)
      : !worker || (workerChange === 'CAPACITY' && workerCapacityInvalid)
  );

  return (
    <section className="rounded-[1.5rem] border border-ops-violet/30 bg-abyss shadow-card p-5 sm:p-6">
      <div className="flex flex-wrap items-center justify-between gap-3">
        <div>
          <p className="text-xs font-mono font-bold uppercase tracking-[0.14em] text-ops-violet">
            Live controls
          </p>
          <h2 className="text-2xl font-extrabold tracking-[-0.035em] text-ink-primary mt-1">
            Change one thing
          </h2>
        </div>
        <div className="flex rounded-xl border border-border-dim bg-deep p-1">
          {([
            ['PROBLEM', 'Problems'],
            ['WORKER', 'Workers'],
          ] as const).map(([value, label]) => (
            <button
              key={value}
              type="button"
              onClick={() => setView(value)}
              className={`rounded-lg px-4 py-2 text-sm font-bold transition-colors focus-ring ${
                view === value
                  ? 'bg-ops-violet text-white'
                  : 'text-ink-muted hover:text-ink-primary'
              }`}
            >
              {label}
            </button>
          ))}
        </div>
      </div>

      {view === 'PROBLEM' ? (
        <div className="mt-5 space-y-4">
          <label className="block">
            <span className="text-xs font-mono font-bold uppercase tracking-[0.12em] text-ink-muted">
              Problem
            </span>
            <select
              value={problemId}
              onChange={(event) => setProblemId(event.target.value)}
              className="mt-2 w-full rounded-xl border border-border-base bg-deep px-4 py-3 text-base font-bold text-ink-primary focus-ring"
            >
              {problems.map((item) => (
                <option key={item.incident_id} value={item.incident_id}>
                  {item.incident_id} · {item.customer_name ?? item.customer_id} · {item.severity}
                </option>
              ))}
            </select>
          </label>

          {problem && (
            <div className="grid grid-cols-3 gap-2">
              {[
                ['SLA', problem.minutes_to_sla === null ? '—' : `${problem.minutes_to_sla}m`],
                ['Effort', `${problem.estimated_effort_minutes ?? '—'}m`],
                ['Priority', problem.priority_rank ?? '—'],
              ].map(([label, value]) => (
                <div key={label} className="rounded-xl border border-border-dim bg-deep p-3">
                  <p className="text-lg font-extrabold text-ink-primary">{value}</p>
                  <p className="text-xs text-ink-muted mt-1">{label}</p>
                </div>
              ))}
            </div>
          )}

          <div className="grid sm:grid-cols-4 gap-2">
            {([
              ['PRIORITY', 'Make critical'],
              ['SLA', 'Change SLA'],
              ['EFFORT', 'Change effort'],
              ['RESOLVE', 'Resolve'],
            ] as const).map(([value, label]) => (
              <button
                key={value}
                type="button"
                onClick={() => setProblemChange(value)}
                className={`rounded-xl border px-3 py-3 text-sm font-bold focus-ring ${
                  problemChange === value
                    ? 'border-ops-violet bg-ops-violet/[0.08] text-ops-violet'
                    : 'border-border-dim bg-deep text-ink-secondary'
                }`}
              >
                {label}
              </button>
            ))}
          </div>

          {problemChange === 'SLA' && (
            <label className="block">
              <span className="text-sm font-bold text-ink-secondary">New deadline</span>
              <select
                value={slaMinutes}
                onChange={(event) => setSlaMinutes(Number(event.target.value))}
                className="mt-2 w-full rounded-xl border border-border-base bg-deep px-4 py-3 text-base font-bold text-ink-primary focus-ring"
              >
                <option value={30}>30 minutes from now</option>
                <option value={45}>45 minutes from now</option>
                <option value={60}>1 hour from now</option>
                <option value={120}>2 hours from now</option>
              </select>
            </label>
          )}

          {problemChange === 'EFFORT' && (
            <label className="block">
              <span className="text-sm font-bold text-ink-secondary">Estimated minutes</span>
              <input
                type="number"
                min={15}
                max={10080}
                step={15}
                value={effortMinutes}
                onChange={(event) => setEffortMinutes(Number(event.target.value))}
                className="mt-2 w-full rounded-xl border border-border-base bg-deep px-4 py-3 text-base font-bold text-ink-primary focus-ring"
              />
            </label>
          )}

          {problemChange === 'PRIORITY' && problemPriorityDisabled && (
            <p className="text-sm text-ops-orange">This problem is already critical. Choose another change.</p>
          )}
        </div>
      ) : (
        <div className="mt-5 space-y-4">
          <label className="block">
            <span className="text-xs font-mono font-bold uppercase tracking-[0.12em] text-ink-muted">
              Worker
            </span>
            <select
              value={workerId}
              onChange={(event) => setWorkerId(event.target.value)}
              className="mt-2 w-full rounded-xl border border-border-base bg-deep px-4 py-3 text-base font-bold text-ink-primary focus-ring"
            >
              {workers.map((item) => (
                <option key={item.specialist_id} value={item.specialist_id}>
                  {item.specialist_name} · {item.availability ? 'Available' : 'Unavailable'}
                </option>
              ))}
            </select>
          </label>

          {worker && (
            <div className="grid grid-cols-3 gap-2">
              {[
                ['Load', workerLoad(worker)],
                ['Free', worker.available_capacity ?? '—'],
                ['Effective', worker.effectiveness_score === null ? '—' : `${worker.effectiveness_score}%`],
              ].map(([label, value]) => (
                <div key={label} className="rounded-xl border border-border-dim bg-deep p-3">
                  <p className="text-lg font-extrabold text-ink-primary">{value}</p>
                  <p className="text-xs text-ink-muted mt-1">{label}</p>
                </div>
              ))}
            </div>
          )}

          {worker && (
            <>
              <div className="grid grid-cols-2 gap-2">
                {([
                  ['AVAILABILITY', worker.availability ? 'Make unavailable' : 'Return to team'],
                  ['CAPACITY', 'Change load'],
                ] as const).map(([value, label]) => (
                  <button
                    key={value}
                    type="button"
                    onClick={() => setWorkerChange(value)}
                    className={`rounded-xl border px-3 py-3 text-sm font-bold focus-ring ${
                      workerChange === value
                        ? 'border-ops-violet bg-ops-violet/[0.08] text-ops-violet'
                        : 'border-border-dim bg-deep text-ink-secondary'
                    }`}
                  >
                    {label}
                  </button>
                ))}
              </div>

              {workerChange === 'AVAILABILITY' ? (
                <div className="rounded-xl border border-border-dim bg-deep px-4 py-3">
                  <p className="text-sm font-bold text-ink-primary">
                    {worker.availability ? 'Remove from today’s team' : 'Restore to today’s team'}
                  </p>
                  <p className="text-sm text-ink-muted mt-1">
                    {worker.skills.length ? worker.skills.join(' · ') : 'No skills recorded'}
                  </p>
                </div>
              ) : (
                <div className="grid sm:grid-cols-2 gap-3">
                  <label className="block">
                    <span className="text-sm font-bold text-ink-secondary">Capacity</span>
                    <input
                      type="number"
                      min={1}
                      max={100}
                      value={workerCapacity}
                      onChange={(event) => setWorkerCapacity(Number(event.target.value))}
                      className="mt-2 w-full rounded-xl border border-border-base bg-deep px-4 py-3 text-base font-bold text-ink-primary focus-ring"
                    />
                  </label>
                  <label className="block">
                    <span className="text-sm font-bold text-ink-secondary">Active work</span>
                    <input
                      type="number"
                      min={0}
                      max={100}
                      value={workerWorkload}
                      onChange={(event) => setWorkerWorkload(Number(event.target.value))}
                      className="mt-2 w-full rounded-xl border border-border-base bg-deep px-4 py-3 text-base font-bold text-ink-primary focus-ring"
                    />
                  </label>
                  {workerCapacityInvalid && (
                    <p className="sm:col-span-2 text-sm text-ops-orange">
                      Active work cannot be greater than capacity.
                    </p>
                  )}
                </div>
              )}
            </>
          )}
        </div>
      )}

      <div className="mt-5 flex flex-wrap items-center justify-between gap-3 border-t border-border-dim pt-4">
        <p className="text-sm text-ink-muted">
          Saved to the real demo services, then available to the decision engine.
        </p>
        <button
          type="button"
          disabled={actionDisabled}
          onClick={() => void (view === 'PROBLEM' ? applyProblemChange() : applyWorkerChange())}
          className="rounded-xl bg-ops-violet px-5 py-3 text-sm font-bold text-white disabled:opacity-35 focus-ring"
        >
          {busy ? 'Applying…' : 'Apply change'}
        </button>
      </div>
    </section>
  );
}
