import { useEffect, useMemo, useState } from 'react';
import { useNavigate } from 'react-router-dom';
import { api } from '../api/client';
import type {
  DemoPortfolio,
  FailureSimulationPayload,
  SimulationState,
  SpecialistResponseSimulationPayload,
} from '../types/api';

type LabView = 'responses' | 'failures' | 'state';

interface Drill {
  id: string;
  title: string;
  signal: string;
  cause: string;
  watch: string;
  lesson: string;
  goal: string;
}

interface ResponseDrill extends Drill {
  payload: SpecialistResponseSimulationPayload;
}

interface FailureDrill extends Drill {
  payload: FailureSimulationPayload;
}

interface ArmedDrill {
  title: string;
  message: string;
  goal: string | null;
  tone: 'success' | 'warning';
}

const RESPONSE_DRILLS: ResponseDrill[] = [
  {
    id: 'accept',
    title: 'Specialist accepts',
    signal: 'Happy path',
    cause: 'The next assignment request receives an explicit acceptance.',
    watch: 'Tentative capacity becomes confirmed, then the incident moves into active work.',
    lesson: 'Consent is the gate between a reversible hold and committed assignment.',
    goal: 'Assign available qualified specialists to incidents closest to SLA breach today, without moving existing confirmed work.',
    payload: {
      status: 'ACCEPTED',
      reason: 'Scenario Lab: specialist accepted the proposed assignment',
      response_delay_seconds: 2,
      apply_once: true,
      expires_after_seconds: 600,
    },
  },
  {
    id: 'reject',
    title: 'Specialist declines',
    signal: 'Replan path',
    cause: 'The next assignment request receives an explicit rejection.',
    watch: 'The tentative reservation is cancelled, the pairing is blocked, and plans are regenerated.',
    lesson: 'A rejected pairing becomes evidence for the next plan, not a reason to force the original.',
    goal: 'Protect high-ARR customers with renewal risk from SLA breach today, while keeping specialist workload below safe capacity.',
    payload: {
      status: 'REJECTED',
      reason: 'Scenario Lab: conflicting on-call responsibility',
      response_delay_seconds: 2,
      apply_once: true,
      expires_after_seconds: 600,
    },
  },
  {
    id: 'slow-accept',
    title: 'Delayed acceptance',
    signal: 'Patience path',
    cause: 'The next specialist accepts, but only after a short response delay.',
    watch: 'The execution relay polls without treating silence as consent.',
    lesson: 'Waiting can be correct: no incident write occurs until an explicit answer arrives.',
    goal: 'Prioritize urgent SLA coverage today while requiring explicit specialist confirmation before any assignment is committed.',
    payload: {
      status: 'ACCEPTED',
      reason: 'Scenario Lab: delayed acknowledgement',
      response_delay_seconds: 4,
      apply_once: true,
      expires_after_seconds: 600,
    },
  },
];

const FAILURE_DRILLS: FailureDrill[] = [
  {
    id: 'crm-unavailable',
    title: 'CRM unavailable once',
    signal: 'Evidence gap',
    cause: 'The next CRM source call returns HTTP 503, then the rule expires.',
    watch: 'Confidence and source status should reveal that commercial evidence is incomplete.',
    lesson: 'ARR and renewal claims must not be presented as current when CRM evidence is unavailable.',
    goal: 'Protect high-ARR renewals from urgent SLA risk today, and show me any evidence gaps before recommending a plan.',
    payload: {
      service: 'crm',
      enabled: true,
      failure_type: 'HTTP_ERROR',
      status_code: 503,
      apply_once: true,
      expires_after_seconds: 600,
      message: 'Scenario Lab: CRM temporarily unavailable',
    },
  },
  {
    id: 'workforce-timeout',
    title: 'Workforce times out once',
    signal: 'Capacity uncertainty',
    cause: 'The next workforce source request times out, then the rule expires.',
    watch: 'Availability and safe-capacity evidence should be marked unavailable or degraded.',
    lesson: 'A safe route cannot infer free capacity from a silent workforce system.',
    goal: 'Assign urgent incidents only when specialist skills, availability, and safe capacity can be verified.',
    payload: {
      service: 'workforce',
      enabled: true,
      failure_type: 'TIMEOUT',
      delay_seconds: 3,
      apply_once: true,
      expires_after_seconds: 600,
      message: 'Scenario Lab: workforce source timed out',
    },
  },
  {
    id: 'incident-invalid',
    title: 'Incident data is invalid once',
    signal: 'Quality guard',
    cause: 'The next Incident source response is deliberately malformed.',
    watch: 'The route should expose the source failure instead of scoring unreliable SLA evidence.',
    lesson: 'A response arriving is not enough; its contract must also be valid.',
    goal: 'Prioritize incidents nearest to SLA breach, but stop and explain if incident evidence is invalid.',
    payload: {
      service: 'incident',
      enabled: true,
      failure_type: 'INVALID_RESPONSE',
      apply_once: true,
      expires_after_seconds: 600,
      message: 'Scenario Lab: invalid incident source response',
    },
  },
];

const VIEW_TABS: { id: LabView; label: string; detail: string }[] = [
  { id: 'responses', label: 'Response drills', detail: 'Acceptance, rejection, and delay' },
  { id: 'failures', label: 'Source failures', detail: 'Evidence and quality safeguards' },
  { id: 'state', label: 'Lab state', detail: 'See what is armed right now' },
];

function recordValue(value: unknown): Record<string, unknown> {
  return value && typeof value === 'object' && !Array.isArray(value)
    ? value as Record<string, unknown>
    : {};
}

function countArray(value: unknown): number {
  return Array.isArray(value) ? value.length : 0;
}

export function DemoLabPage() {
  const navigate = useNavigate();
  const [view, setView] = useState<LabView>('responses');
  const [portfolio, setPortfolio] = useState<DemoPortfolio | null>(null);
  const [simulation, setSimulation] = useState<SimulationState | null>(null);
  const [loading, setLoading] = useState(true);
  const [busyId, setBusyId] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [armed, setArmed] = useState<ArmedDrill | null>(null);

  const refresh = async () => {
    const [nextPortfolio, nextSimulation] = await Promise.all([
      api.getDemoPortfolio(),
      api.getSimulationState(),
    ]);
    setPortfolio(nextPortfolio);
    setSimulation(nextSimulation);
  };

  useEffect(() => {
    let cancelled = false;
    const load = async () => {
      try {
        const [nextPortfolio, nextSimulation] = await Promise.all([
          api.getDemoPortfolio(),
          api.getSimulationState(),
        ]);
        if (cancelled) return;
        setPortfolio(nextPortfolio);
        setSimulation(nextSimulation);
      } catch (err: unknown) {
        if (!cancelled) {
          setError(err instanceof Error ? err.message : 'The Scenario Lab could not connect');
        }
      } finally {
        if (!cancelled) setLoading(false);
      }
    };
    void load();
    return () => {
      cancelled = true;
    };
  }, []);

  const labCounts = useMemo(() => {
    const communication = recordValue(simulation?.communication);
    const queuedResponses = countArray(communication.queued_specialist_responses);
    const communicationFailures = countArray(communication.active_failure_modes);
    const sourceFailures = Object.values(simulation?.services ?? {}).filter(
      (value) => recordValue(value).enabled === true,
    ).length;
    return {
      queuedResponses,
      activeFailures: communicationFailures + sourceFailures,
    };
  }, [simulation]);

  const armResponse = async (drill: ResponseDrill) => {
    setBusyId(drill.id);
    setError(null);
    try {
      await api.queueSpecialistResponse(drill.payload);
      await refresh();
      setArmed({
        title: drill.title,
        message: 'The next matching assignment request will consume this response once.',
        goal: drill.goal,
        tone: drill.payload.status === 'REJECTED' ? 'warning' : 'success',
      });
    } catch (err: unknown) {
      setError(err instanceof Error ? err.message : 'The response drill could not be armed');
    } finally {
      setBusyId(null);
    }
  };

  const armFailure = async (drill: FailureDrill) => {
    setBusyId(drill.id);
    setError(null);
    try {
      await api.configureFailure(drill.payload);
      await refresh();
      setArmed({
        title: drill.title,
        message: 'The failure is active for the next matching source call and expires automatically.',
        goal: drill.goal,
        tone: 'warning',
      });
    } catch (err: unknown) {
      setError(err instanceof Error ? err.message : 'The source failure could not be armed');
    } finally {
      setBusyId(null);
    }
  };

  const resetLab = async () => {
    setBusyId('reset');
    setError(null);
    try {
      const result = await api.resetDemo();
      await refresh();
      setArmed({
        title: result.degraded ? 'Reset completed with warnings' : 'Baseline restored',
        message: result.degraded
          ? 'At least one service could not be reset. Review Lab state before continuing.'
          : 'CRM, Incident, Workforce, and Communication returned to deterministic demo data.',
        goal: null,
        tone: result.degraded ? 'warning' : 'success',
      });
    } catch (err: unknown) {
      setError(err instanceof Error ? err.message : 'The lab could not be reset');
    } finally {
      setBusyId(null);
    }
  };

  const startGoal = (goal: string) => {
    try {
      sessionStorage.setItem('optiflow_goal_draft', goal);
    } catch {
      // Today still opens if browser storage is unavailable.
    }
    navigate('/');
  };

  const portfolioSummary = portfolio?.portfolio_summary;

  return (
    <div className="min-h-full paper-noise">
      <section className="border-b border-border-dim bg-abyss">
        <div className="max-w-7xl mx-auto px-5 sm:px-8 py-10 lg:py-14">
          <div className="grid lg:grid-cols-[minmax(0,1fr)_360px] gap-8 items-end">
            <div>
              <p className="text-[9px] font-mono font-semibold uppercase tracking-[0.2em] text-ops-violet">
                Controlled scenario lab
              </p>
              <h1 className="max-w-4xl text-4xl sm:text-6xl font-extrabold tracking-[-0.06em] leading-[0.98] mt-4">
                Change one condition.
                <span className="block text-ops-violet">Understand the whole route.</span>
              </h1>
              <p className="max-w-2xl text-sm sm:text-base leading-relaxed text-ink-secondary mt-5">
                Arm a single controlled behavior, run a goal through the real demo APIs, then inspect
                which card changed and why.
              </p>
            </div>
            <aside className="rounded-2xl border border-border-dim bg-deep p-5">
              <div className="flex items-start justify-between gap-4">
                <div>
                  <p className="text-[8px] font-mono font-semibold uppercase tracking-[0.16em] text-ink-muted">
                    Lab safety boundary
                  </p>
                  <p className="text-sm font-bold text-ink-primary mt-2">Demo services only</p>
                </div>
                <span className={`mt-1 w-2.5 h-2.5 rounded-full ${
                  simulation?.degraded ? 'bg-ops-orange' : 'bg-ops-emerald'
                }`} />
              </div>
              <p className="text-[10px] leading-relaxed text-ink-muted mt-2">
                Drills change the isolated demo state. They do not call production systems.
              </p>
              <button
                type="button"
                onClick={() => void resetLab()}
                disabled={busyId !== null}
                className="mt-4 w-full rounded-xl border border-border-base bg-abyss px-4 py-3 text-[10px] font-bold text-ink-secondary hover:text-ops-violet disabled:opacity-50 focus-ring"
              >
                {busyId === 'reset' ? 'Restoring baseline…' : 'Reset all demo services'}
              </button>
            </aside>
          </div>
        </div>
      </section>

      <section className="max-w-7xl mx-auto px-5 sm:px-8 py-8 lg:py-10">
        <div className="grid grid-cols-2 lg:grid-cols-4 gap-3">
          {[
            ['Customers', portfolioSummary?.total_customers ?? '—'],
            ['Active incidents', portfolioSummary?.total_active_incidents ?? '—'],
            ['Queued responses', labCounts.queuedResponses],
            ['Active failures', labCounts.activeFailures],
          ].map(([label, value]) => (
            <div key={label} className="rounded-2xl border border-border-dim bg-abyss p-4">
              <p className="text-[8px] font-mono uppercase tracking-[0.14em] text-ink-muted">{label}</p>
              <p className="text-2xl font-extrabold text-ink-primary mt-2">{loading ? '…' : value}</p>
            </div>
          ))}
        </div>

        {error && (
          <div className="mt-5 rounded-xl border border-ops-rose/30 bg-ops-rose/[0.055] px-4 py-3 text-xs text-ops-rose" role="alert">
            {error}
          </div>
        )}

        {armed && (
          <div className={`mt-5 rounded-2xl border p-5 ${
            armed.tone === 'success'
              ? 'border-ops-emerald/30 bg-ops-emerald/[0.055]'
              : 'border-ops-violet/35 bg-ops-violet/[0.06]'
          }`}>
            <div className="flex flex-col sm:flex-row sm:items-center sm:justify-between gap-4">
              <div>
                <p className="text-[8px] font-mono font-semibold uppercase tracking-[0.16em] text-ink-muted">
                  Lab condition armed
                </p>
                <h2 className="text-sm font-extrabold text-ink-primary mt-1.5">{armed.title}</h2>
                <p className="text-[10px] leading-relaxed text-ink-secondary mt-1">{armed.message}</p>
              </div>
              {armed.goal && (
                <button
                  type="button"
                  onClick={() => startGoal(armed.goal as string)}
                  className="shrink-0 rounded-xl bg-ink-primary px-4 py-3 text-[10px] font-bold text-white hover:bg-ops-violet focus-ring"
                >
                  Start the matching goal &rarr;
                </button>
              )}
            </div>
          </div>
        )}

        <div className="grid sm:grid-cols-3 gap-3 mt-6" role="tablist" aria-label="Scenario Lab views">
          {VIEW_TABS.map((tab) => (
            <button
              key={tab.id}
              type="button"
              role="tab"
              aria-selected={view === tab.id}
              onClick={() => setView(tab.id)}
              className={`rounded-2xl border p-4 text-left transition-all focus-ring ${
                view === tab.id
                  ? 'border-ops-violet bg-ops-violet/[0.06] shadow-card'
                  : 'border-border-dim bg-abyss hover:border-border-base'
              }`}
            >
              <p className={`text-[10px] font-bold ${view === tab.id ? 'text-ops-violet' : 'text-ink-secondary'}`}>
                {tab.label}
              </p>
              <p className="text-[9px] leading-relaxed text-ink-muted mt-1.5">{tab.detail}</p>
            </button>
          ))}
        </div>

        {view !== 'state' ? (
          <div className="grid lg:grid-cols-3 gap-4 mt-6">
            {(view === 'responses' ? RESPONSE_DRILLS : FAILURE_DRILLS).map((drill) => (
              <article key={drill.id} className="rounded-[1.5rem] border border-border-dim bg-abyss shadow-card overflow-hidden">
                <div className={`h-1 ${view === 'responses' ? 'bg-ops-cyan' : 'bg-ops-violet'}`} />
                <div className="p-5">
                  <p className={`text-[8px] font-mono font-semibold uppercase tracking-[0.15em] ${
                    view === 'responses' ? 'text-ops-cyan' : 'text-ops-violet'
                  }`}>
                    {drill.signal}
                  </p>
                  <h2 className="text-base font-extrabold tracking-[-0.025em] text-ink-primary mt-2">
                    {drill.title}
                  </h2>
                  <div className="space-y-3 mt-5">
                    {[
                      ['Cause', drill.cause],
                      ['Watch', drill.watch],
                      ['What it teaches', drill.lesson],
                    ].map(([label, value]) => (
                      <div key={label} className="rounded-xl border border-border-dim bg-deep/55 p-3.5">
                        <p className="text-[8px] font-mono font-semibold uppercase tracking-[0.13em] text-ink-muted">{label}</p>
                        <p className="text-[10px] leading-relaxed text-ink-secondary mt-1.5">{value}</p>
                      </div>
                    ))}
                  </div>
                  <button
                    type="button"
                    disabled={busyId !== null}
                    onClick={() => view === 'responses'
                      ? void armResponse(drill as ResponseDrill)
                      : void armFailure(drill as FailureDrill)}
                    className="mt-5 w-full rounded-xl bg-ink-primary px-4 py-3 text-[10px] font-bold text-white hover:bg-ops-violet disabled:opacity-50 focus-ring"
                  >
                    {busyId === drill.id ? 'Arming condition…' : `Arm ${drill.title.toLowerCase()}`}
                  </button>
                </div>
              </article>
            ))}
          </div>
        ) : (
          <div className="grid lg:grid-cols-[minmax(0,1fr)_320px] gap-5 mt-6">
            <div className="rounded-[1.5rem] border border-border-dim bg-abyss p-5 sm:p-6">
              <p className="text-[8px] font-mono font-semibold uppercase tracking-[0.16em] text-ops-violet">
                Source readiness
              </p>
              <div className="grid sm:grid-cols-2 gap-3 mt-4">
                {(portfolio?.sources ?? []).map((source) => (
                  <div key={source.source_name} className="rounded-xl border border-border-dim bg-deep/55 p-4">
                    <div className="flex items-center justify-between gap-3">
                      <span className="text-[10px] font-bold text-ink-primary">
                        {source.source_name.replace(/_/g, ' ')}
                      </span>
                      <span className={`w-2 h-2 rounded-full ${
                        source.status === 'AVAILABLE' ? 'bg-ops-emerald' : 'bg-ops-orange'
                      }`} />
                    </div>
                    <p className="text-[9px] font-mono text-ink-muted mt-2">
                      {source.status} · {source.response_time_ms?.toFixed(0) ?? '—'} ms
                    </p>
                  </div>
                ))}
              </div>
            </div>
            <aside className="rounded-[1.5rem] border border-border-dim bg-deep p-5">
              <p className="text-[8px] font-mono font-semibold uppercase tracking-[0.16em] text-ink-muted">
                What is armed
              </p>
              <div className="space-y-3 mt-4">
                <div className="rounded-xl border border-border-dim bg-abyss p-4">
                  <p className="text-2xl font-extrabold text-ops-cyan">{labCounts.queuedResponses}</p>
                  <p className="text-[10px] text-ink-muted mt-1">queued specialist responses</p>
                </div>
                <div className="rounded-xl border border-border-dim bg-abyss p-4">
                  <p className="text-2xl font-extrabold text-ops-violet">{labCounts.activeFailures}</p>
                  <p className="text-[10px] text-ink-muted mt-1">active source failure rules</p>
                </div>
              </div>
              <p className="text-[9px] leading-relaxed text-ink-muted mt-4">
                Use reset when you want deterministic baseline data before another walkthrough.
              </p>
            </aside>
          </div>
        )}
      </section>
    </div>
  );
}
