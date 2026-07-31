interface DecisionJourneyRailProps {
  activeId: string;
  selectedId: string | null;
  failed: boolean;
  onSelect: (stageId: string | null) => void;
}

type JourneyState = 'complete' | 'active' | 'waiting' | 'failed';

const STAGE_ALIASES: Record<string, string> = {
  clarify: 'validate',
  failed: 'complete',
};

const NODES = [
  { id: 'receive', label: 'Goal' },
  { id: 'interpret', label: 'Interpret' },
  { id: 'validate', label: 'Guard' },
  { id: 'evidence', label: 'Evidence' },
  { id: 'optimize', label: 'Plans' },
  { id: 'approval', label: 'Choose' },
  { id: 'executing', label: 'Execute' },
  { id: 'complete', label: 'Verify' },
] as const;

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
    <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2.2" className="h-5 w-5" aria-hidden="true">
      <path d="m5 12 4 4L19 6" strokeLinecap="round" strokeLinejoin="round" />
    </svg>
  );
}

export function normalizeJourneyStage(stageId: string): string {
  return STAGE_ALIASES[stageId] ?? stageId;
}

export function DecisionJourneyRail({
  activeId,
  selectedId,
  failed,
  onSelect,
}: DecisionJourneyRailProps) {
  const normalizedActiveId = normalizeJourneyStage(activeId);
  const activeIndex = Math.max(
    NODES.findIndex((node) => node.id === normalizedActiveId),
    0,
  );
  const journeyComplete = normalizedActiveId === 'complete' && !failed;
  const inspectedId = selectedId ?? normalizedActiveId;

  return (
    <nav aria-label="Decision path">
      <div className="mb-3 flex flex-wrap items-center justify-between gap-3">
        <div className="flex items-center gap-2">
          <p className="text-sm font-bold text-ink-secondary">Decision path</p>
          <span className="rounded-full bg-ops-cyan/10 px-2.5 py-1 text-xs font-bold text-ops-cyan">
            {journeyComplete ? NODES.length : activeIndex + 1}/{NODES.length}
          </span>
        </div>
        <p className="text-sm text-ink-muted">
          Select a step to inspect its data and reason.
        </p>
      </div>

      <div className="-mx-2 overflow-x-auto px-2 pb-2">
        <div className="relative min-w-[760px] rounded-2xl border border-border-dim bg-deep/45 px-5 py-4">
          <div className="absolute left-[7%] right-[7%] top-[40px] h-0.5 bg-border-base" />
          <div
            className="absolute left-[7%] top-[40px] h-0.5 bg-ops-cyan transition-all duration-700"
            style={{ width: `${(activeIndex / (NODES.length - 1)) * 86}%` }}
          />

          <div className="relative grid grid-cols-8 gap-3">
            {NODES.map((node, index) => {
              const state = stateForNode(index, activeIndex, journeyComplete, failed);
              const selected = node.id === inspectedId;
              const circle = state === 'complete'
                ? 'border-ops-cyan bg-ops-cyan text-white'
                : state === 'active'
                  ? 'border-ops-amber bg-ops-amber text-white shadow-amber-glow'
                  : state === 'failed'
                    ? 'border-ops-rose bg-ops-rose text-white'
                    : 'border-border-base bg-deep text-ink-muted';
              const label = state === 'active'
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
                  aria-current={state === 'active' ? 'step' : undefined}
                  aria-pressed={selected}
                  className="relative z-10 flex min-h-20 min-w-0 flex-col items-center rounded-xl text-center focus-ring"
                >
                  <span className="relative h-12 w-12">
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
                  <span className={`mt-2 text-sm font-extrabold ${label}`}>{node.label}</span>
                </button>
              );
            })}
          </div>
        </div>
      </div>
    </nav>
  );
}
