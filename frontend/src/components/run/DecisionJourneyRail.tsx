import type { DemoPortfolio, RunSummary } from '../../types/api';

interface DecisionJourneyRailProps {
  activeId: string;
  selectedId: string | null;
  failed: boolean;
  portfolio: DemoPortfolio | null;
  runData: RunSummary | null;
  onSelect: (stageId: string | null) => void;
}

type JourneyState = 'complete' | 'active' | 'waiting' | 'failed';

interface JourneyNode {
  id: string;
  label: string;
  reason: string;
}

const STAGE_ALIASES: Record<string, string> = {
  clarify: 'validate',
  failed: 'complete',
};

const NODES: JourneyNode[] = [
  { id: 'receive', label: 'Goal', reason: 'Create one traceable decision run.' },
  { id: 'interpret', label: 'Interpret', reason: 'Turn human direction into objectives and constraints.' },
  { id: 'validate', label: 'Guard', reason: 'Stop ambiguity and policy conflicts before planning.' },
  { id: 'evidence', label: 'Evidence', reason: 'Fetch current customer, incident, team, and communication data.' },
  { id: 'optimize', label: 'Plans', reason: 'Compare safe allocation trade-offs under the same constraints.' },
  { id: 'approval', label: 'Choose', reason: 'Keep execution behind an explicit human decision.' },
  { id: 'executing', label: 'Execute', reason: 'Apply the approved plan with verified, reversible writes.' },
  { id: 'complete', label: 'Verify', reason: 'Confirm every expected outcome and close the audit trail.' },
];

const BRANCHES: Record<string, Array<{ label: string; detail: string; tone: string }>> = {
  validate: [
    { label: 'Continue', detail: 'Goal is safe and complete', tone: 'border-ops-emerald/35 text-ops-emerald' },
    { label: 'Clarify', detail: 'Ask the human; do not guess', tone: 'border-ops-orange/35 text-ops-orange' },
    { label: 'Safe stop', detail: 'A policy conflict remains', tone: 'border-ops-rose/35 text-ops-rose' },
  ],
  approval: [
    { label: 'Approve', detail: 'Execute the selected plan', tone: 'border-ops-emerald/35 text-ops-emerald' },
    { label: 'Modify', detail: 'Return to planning', tone: 'border-ops-violet/35 text-ops-violet' },
    { label: 'Reject', detail: 'Close without operational writes', tone: 'border-ops-rose/35 text-ops-rose' },
  ],
};

function stateForNode(
  index: number,
  activeIndex: number,
  journeyComplete: boolean,
  failed: boolean,
): JourneyState {
  if (failed && index === activeIndex) return 'failed';
  if (journeyComplete || index < activeIndex) return 'complete';
  if (index === activeIndex) return 'active';
  return 'waiting';
}

function CheckIcon() {
  return (
    <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2.2" className="h-5 w-5">
      <path d="m5 12 4 4L19 6" strokeLinecap="round" strokeLinejoin="round" />
    </svg>
  );
}

function DataBadges({
  nodeId,
  portfolio,
  runData,
}: {
  nodeId: string;
  portfolio: DemoPortfolio | null;
  runData: RunSummary | null;
}) {
  if (nodeId === 'evidence') {
    const summary = portfolio?.portfolio_summary;
    const badges = [
      ['CRM', summary?.total_customers == null ? 'waiting' : `${summary.total_customers} clients`],
      ['Risks', summary?.total_active_incidents == null ? 'waiting' : `${summary.total_active_incidents} active`],
      ['Team', summary?.total_specialists == null ? 'waiting' : `${summary.available_specialists ?? 0}/${summary.total_specialists} ready`],
      ['Comms', runData?.selected_tools.some((tool) => tool.selected && tool.toolName.toLowerCase().includes('communication')) ? 'selected' : 'standby'],
    ];

    return (
      <div>
        <p className="text-xs font-bold uppercase tracking-[0.12em] text-ink-muted">Data fetched</p>
        <div className="mt-3 flex flex-wrap gap-2">
          {badges.map(([label, value]) => (
            <span key={label} className="rounded-full border border-border-base bg-deep px-3 py-1.5 text-xs text-ink-secondary">
              <strong className="text-ops-cyan">{label}</strong> · {value}
            </span>
          ))}
        </div>
      </div>
    );
  }

  if (nodeId === 'optimize') {
    return (
      <div>
        <p className="text-xs font-bold uppercase tracking-[0.12em] text-ink-muted">Candidate plans</p>
        <div className="mt-3 flex flex-wrap gap-2">
          {(runData?.candidate_plans ?? []).slice(0, 4).map((plan) => (
            <span key={plan.plan_id} className="rounded-full border border-ops-violet/30 bg-ops-violet/[0.06] px-3 py-1.5 text-xs text-ink-secondary">
              <strong className="text-ops-violet">{plan.profile.replace(/_/g, ' ')}</strong>
              {' '}· {plan.metrics.assigned_count} placed
            </span>
          ))}
          {!runData?.candidate_plans.length && (
            <span className="text-sm text-ink-muted">Plans appear when optimization completes.</span>
          )}
        </div>
      </div>
    );
  }

  return null;
}

export function normalizeJourneyStage(stageId: string): string {
  return STAGE_ALIASES[stageId] ?? stageId;
}

export function DecisionJourneyRail({
  activeId,
  selectedId,
  failed,
  portfolio,
  runData,
  onSelect,
}: DecisionJourneyRailProps) {
  const normalizedActiveId = normalizeJourneyStage(activeId);
  const activeIndex = Math.max(
    NODES.findIndex((node) => node.id === normalizedActiveId),
    0,
  );
  const journeyComplete = normalizedActiveId === 'complete' && !failed;
  const inspectedId = selectedId ?? normalizedActiveId;
  const inspectedNode = NODES.find((node) => node.id === inspectedId) ?? NODES[activeIndex];
  const inspectedIndex = NODES.findIndex((node) => node.id === inspectedNode.id);
  const inspectedState = stateForNode(inspectedIndex, activeIndex, journeyComplete, failed);
  const branches = BRANCHES[inspectedNode.id] ?? [];

  return (
    <nav aria-label="Decision path">
      <div className="mb-4 flex flex-wrap items-end justify-between gap-3">
        <div>
          <div className="flex items-center gap-2">
            <p className="text-xs font-bold uppercase tracking-[0.16em] text-ink-secondary">Decision path</p>
            <span className="rounded-full bg-ops-cyan/10 px-2.5 py-1 text-xs font-bold text-ops-cyan">
              {journeyComplete ? NODES.length : activeIndex + 1}/{NODES.length}
            </span>
          </div>
          <p className="mt-1 text-sm text-ink-muted">Select a step to inspect its reason and data.</p>
        </div>
        {selectedId && (
          <button
            type="button"
            onClick={() => onSelect(null)}
            className="rounded-lg text-sm font-bold text-ops-amber hover:underline focus-ring"
          >
            Back to live step
          </button>
        )}
      </div>

      <div className="-mx-2 overflow-x-auto px-2 pb-3">
        <div className="relative min-w-[880px] rounded-2xl border border-border-dim bg-deep/45 px-6 py-5">
          <div className="absolute left-[7%] right-[7%] top-[49px] h-0.5 bg-border-base" />
          <div
            className="absolute left-[7%] top-[49px] h-0.5 bg-ops-cyan transition-all duration-700"
            style={{ width: `${(activeIndex / (NODES.length - 1)) * 86}%` }}
          />

          <div className="relative grid grid-cols-8 gap-4">
            {NODES.map((node, index) => {
              const state = stateForNode(index, activeIndex, journeyComplete, failed);
              const selected = node.id === inspectedNode.id;
              const circle = state === 'complete'
                ? 'border-ops-cyan bg-ops-cyan text-white'
                : state === 'active'
                  ? 'border-ops-amber bg-ops-amber text-white shadow-amber-glow'
                  : state === 'failed'
                    ? 'border-ops-rose bg-ops-rose text-white'
                    : 'border-border-base bg-deep text-ink-muted';
              const text = state === 'active'
                ? 'text-ops-amber'
                : state === 'complete'
                  ? 'text-ops-cyan'
                  : state === 'failed'
                    ? 'text-ops-rose'
                    : 'text-ink-muted';

              return (
                <button
                  key={node.id}
                  type="button"
                  onClick={() => onSelect(node.id === normalizedActiveId ? null : node.id)}
                  aria-pressed={selected}
                  className="relative z-10 flex min-w-0 flex-col items-center rounded-xl text-center focus-ring"
                >
                  <span className="relative h-14 w-14">
                    {state === 'active' && (
                      <span className="absolute -inset-1.5 animate-spin-slow rounded-full border border-dashed border-ops-amber" />
                    )}
                    {selected && (
                      <span className="absolute -inset-2 rounded-full border-2 border-ops-amber/30" />
                    )}
                    <span className={`absolute inset-0 flex items-center justify-center rounded-full border-2 text-xs font-bold ${circle}`}>
                      {state === 'complete' ? <CheckIcon /> : state === 'failed' ? '×' : String(index + 1).padStart(2, '0')}
                    </span>
                  </span>
                  <span className={`mt-3 text-sm font-extrabold ${text}`}>{node.label}</span>
                  <span className="mt-1 text-xs text-ink-muted">
                    {state === 'active' ? 'Now' : state === 'complete' ? 'Done' : state === 'failed' ? 'Stopped' : 'Wait'}
                  </span>
                </button>
              );
            })}
          </div>
        </div>
      </div>

      <section className="mt-1 rounded-2xl border border-border-base bg-abyss p-5 animate-fade-in">
        <div className="flex flex-wrap items-start justify-between gap-4">
          <div>
            <p className="text-xs font-bold uppercase tracking-[0.14em] text-ops-amber">
              Step {inspectedIndex + 1} · {inspectedState}
            </p>
            <h2 className="mt-1 text-xl font-extrabold text-ink-primary">{inspectedNode.label}</h2>
          </div>
          <p className="max-w-2xl text-sm leading-relaxed text-ink-secondary">
            {inspectedNode.reason}
          </p>
        </div>

        {(branches.length > 0 || inspectedNode.id === 'evidence' || inspectedNode.id === 'optimize') && (
          <div className="mt-5 border-t border-border-dim pt-4">
            {branches.length > 0 && (
              <div className="mb-4">
                <p className="text-xs font-bold uppercase tracking-[0.12em] text-ink-muted">Possible decisions</p>
                <div className="mt-3 grid gap-2 sm:grid-cols-3">
                  {branches.map((branch) => (
                    <div key={branch.label} className={`rounded-xl border bg-deep px-4 py-3 ${branch.tone}`}>
                      <p className="text-sm font-extrabold">{branch.label}</p>
                      <p className="mt-1 text-xs text-ink-muted">{branch.detail}</p>
                    </div>
                  ))}
                </div>
              </div>
            )}
            <DataBadges nodeId={inspectedNode.id} portfolio={portfolio} runData={runData} />
          </div>
        )}
      </section>
    </nav>
  );
}
