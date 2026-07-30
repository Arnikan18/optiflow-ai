import { PHASE_TIMELINE } from '../../data/guideContent';

interface DecisionJourneyRailProps {
  activeId: string;
  selectedId: string | null;
  failed: boolean;
  onSelect: (stageId: string | null) => void;
}

type JourneyState = 'complete' | 'active' | 'waiting' | 'failed';

interface MapNode {
  id: string;
  label: string;
  shortLabel: string;
  x: number;
  y: number;
}

const STAGE_ALIASES: Record<string, string> = {
  clarify: 'validate',
  failed: 'complete',
};

const MAP_NODES: MapNode[] = [
  { id: 'receive', label: 'Goal received', shortLabel: 'Goal', x: 65, y: 168 },
  { id: 'interpret', label: 'Interpret intent', shortLabel: 'Interpret', x: 210, y: 168 },
  { id: 'validate', label: 'Guard policies', shortLabel: 'Guard', x: 355, y: 168 },
  { id: 'evidence', label: 'Pull evidence', shortLabel: 'Evidence', x: 505, y: 168 },
  { id: 'optimize', label: 'Compare plans', shortLabel: 'Plans', x: 655, y: 168 },
  { id: 'approval', label: 'Human decision', shortLabel: 'Choose', x: 820, y: 168 },
  { id: 'executing', label: 'Execute safely', shortLabel: 'Execute', x: 985, y: 168 },
  { id: 'complete', label: 'Verify outcome', shortLabel: 'Verify', x: 1130, y: 168 },
];

const BRANCHES = [
  {
    id: 'clarify',
    label: 'Clarify',
    detail: 'Human answer',
    x: 355,
    y: 48,
    tone: 'orange',
    parent: 'validate',
  },
  {
    id: 'safe-stop',
    label: 'Safe stop',
    detail: 'No unsafe guess',
    x: 355,
    y: 302,
    tone: 'rose',
    parent: 'validate',
  },
  {
    id: 'modify',
    label: 'Modify',
    detail: 'Replan loop',
    x: 820,
    y: 48,
    tone: 'violet',
    parent: 'approval',
  },
  {
    id: 'reject',
    label: 'Reject',
    detail: 'Close safely',
    x: 820,
    y: 302,
    tone: 'rose',
    parent: 'approval',
  },
] as const;

const SOURCE_CHIPS = [
  { label: 'CRM', x: 445, tone: 'violet' },
  { label: 'INC', x: 485, tone: 'rose' },
  { label: 'TEAM', x: 530, tone: 'cyan' },
  { label: 'COMMS', x: 580, tone: 'orange' },
] as const;

const PLAN_CHIPS = [
  { label: 'SLA', tone: 'rose' },
  { label: 'ARR', tone: 'violet' },
  { label: 'FAIR', tone: 'cyan' },
  { label: 'BAL', tone: 'emerald' },
] as const;

const TONE_CLASSES = {
  cyan: 'border-ops-cyan/40 bg-ops-cyan/10 text-ops-cyan',
  emerald: 'border-ops-emerald/40 bg-ops-emerald/10 text-ops-emerald',
  orange: 'border-ops-orange/40 bg-ops-orange/10 text-ops-orange',
  rose: 'border-ops-rose/40 bg-ops-rose/10 text-ops-rose',
  violet: 'border-ops-violet/40 bg-ops-violet/10 text-ops-violet',
} as const;

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

function NodeGlyph({ state, index }: { state: JourneyState; index: number }) {
  if (state === 'complete') {
    return (
      <svg viewBox="0 0 24 24" className="w-5 h-5" fill="none" stroke="currentColor" strokeWidth="2">
        <path d="m5 12 4 4L19 6" strokeLinecap="round" strokeLinejoin="round" />
      </svg>
    );
  }
  if (state === 'failed') {
    return <span className="text-lg leading-none">×</span>;
  }
  return <span>{String(index + 1).padStart(2, '0')}</span>;
}

function MapNodeButton({
  node,
  index,
  state,
  selected,
  onSelect,
}: {
  node: MapNode;
  index: number;
  state: JourneyState;
  selected: boolean;
  onSelect: () => void;
}) {
  const circleStyle = state === 'complete'
    ? 'border-ops-cyan bg-ops-cyan text-white'
    : state === 'active'
      ? 'border-ops-amber bg-ops-amber text-white shadow-amber-glow'
      : state === 'failed'
        ? 'border-ops-rose bg-ops-rose text-white'
        : 'border-border-base bg-deep text-ink-muted';
  const labelStyle = state === 'active'
    ? 'text-ops-amber'
    : state === 'failed'
      ? 'text-ops-rose'
      : state === 'complete'
        ? 'text-ops-cyan'
        : 'text-ink-muted';

  return (
    <button
      type="button"
      onClick={onSelect}
      aria-pressed={selected}
      aria-label={`${node.label}, ${state}`}
      className="absolute z-20 w-[92px] -translate-x-1/2 -translate-y-1/2 flex flex-col items-center focus-ring rounded-xl"
      style={{ left: node.x, top: node.y }}
    >
      <span className="relative w-[58px] h-[58px]">
        {state === 'active' && (
          <span className="absolute -inset-1.5 rounded-full border border-dashed border-ops-amber animate-spin-slow" />
        )}
        {selected && (
          <span className="absolute -inset-2.5 rounded-full border-2 border-ops-amber/30" />
        )}
        <span className={`absolute inset-0 rounded-full border-2 flex items-center justify-center text-[10px] font-mono font-bold transition-all ${circleStyle}`}>
          <NodeGlyph state={state} index={index} />
        </span>
      </span>
      <span className={`text-[9px] font-bold leading-tight mt-2 ${labelStyle}`}>
        {node.shortLabel}
      </span>
      <span className="text-[7px] font-mono text-ink-ghost mt-0.5">
        {state === 'active' ? 'NOW' : state === 'complete' ? 'DONE' : state === 'failed' ? 'STOP' : 'WAIT'}
      </span>
    </button>
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
    MAP_NODES.findIndex((node) => node.id === normalizedActiveId),
    0,
  );
  const journeyComplete = normalizedActiveId === 'complete' && !failed;
  const placedCount = journeyComplete ? MAP_NODES.length : activeIndex + 1;
  const activeNode = MAP_NODES[activeIndex];
  const activeX = activeNode?.x ?? MAP_NODES[0].x;
  const clarificationActive = activeId === 'clarify';

  return (
    <nav aria-label="Decision map" className="mt-1">
      <div className="flex flex-wrap items-end justify-between gap-3 mb-3">
        <div>
          <div className="flex items-center gap-2">
            <p className="text-[8px] font-mono font-semibold uppercase tracking-[0.18em] text-ink-muted">
              Live decision map
            </p>
            <span className="rounded-full bg-ops-cyan/10 px-2 py-1 text-[7px] font-mono font-semibold text-ops-cyan">
              {placedCount}/{PHASE_TIMELINE.length}
            </span>
          </div>
          <p className="text-[9px] text-ink-muted mt-1">
            Select a node to inspect its evidence. Alternate routes stay visible.
          </p>
        </div>
        {selectedId && selectedId !== normalizedActiveId && (
          <button
            type="button"
            onClick={() => onSelect(null)}
            className="text-[9px] font-semibold text-ops-amber hover:underline focus-ring rounded"
          >
            Return to live node →
          </button>
        )}
      </div>

      <div className="overflow-x-auto -mx-2 px-2 pb-2">
        <div className="relative min-w-[1195px] h-[350px] rounded-[1.4rem] border border-border-dim bg-deep/40 overflow-hidden">
          <div className="absolute inset-0 bg-grid-ops opacity-50" />
          <svg
            viewBox="0 0 1195 350"
            preserveAspectRatio="none"
            className="absolute inset-0 w-full h-full"
            aria-hidden="true"
          >
            <line x1="65" y1="168" x2="1130" y2="168" className="stroke-border-base" strokeWidth="2" />
            <line
              x1="65"
              y1="168"
              x2={activeX}
              y2="168"
              className="stroke-ops-cyan transition-all duration-700"
              strokeWidth="3"
            />
            {!journeyComplete && !failed && (
              <line
                x1={Math.max(65, activeX - 70)}
                y1="168"
                x2={activeX}
                y2="168"
                className="decision-map-flow stroke-ops-amber"
                strokeWidth="3"
              />
            )}

            <path d="M355 139 C355 105 355 90 355 75 H505 V139" fill="none" className="stroke-border-base" strokeWidth="1.5" strokeDasharray="5 6" />
            <path d="M355 197 V274" fill="none" className="stroke-ops-rose/35" strokeWidth="1.5" strokeDasharray="5 6" />
            <path d="M820 139 V75 H655 V139" fill="none" className="stroke-ops-violet/45" strokeWidth="1.5" strokeDasharray="5 6" />
            <path d="M820 197 V274" fill="none" className="stroke-ops-rose/35" strokeWidth="1.5" strokeDasharray="5 6" />

            {clarificationActive && (
              <path d="M355 139 C355 105 355 90 355 75 H505 V139" fill="none" className="decision-map-flow stroke-ops-orange" strokeWidth="3" />
            )}

            {SOURCE_CHIPS.map((source) => (
              <path
                key={source.label}
                d={`M${source.x} 262 C${source.x} 225 505 225 505 198`}
                fill="none"
                className={activeIndex === 3 ? 'decision-map-flow stroke-ops-cyan' : 'stroke-border-dim'}
                strokeWidth={activeIndex === 3 ? 2 : 1}
                strokeDasharray="4 6"
              />
            ))}

            <path d="M655 197 V240" fill="none" className="stroke-border-base" strokeWidth="1.5" />
            <path d="M610 240 H700" fill="none" className="stroke-border-base" strokeWidth="1.5" />
          </svg>

          {MAP_NODES.map((node, index) => {
            const state = stateForNode(index, activeIndex, journeyComplete, failed);
            const selected = selectedId === node.id
              || (!selectedId && node.id === normalizedActiveId);
            return (
              <MapNodeButton
                key={node.id}
                node={node}
                index={index}
                state={state}
                selected={selected}
                onSelect={() => onSelect(node.id === normalizedActiveId ? null : node.id)}
              />
            );
          })}

          {BRANCHES.map((branch) => {
            const branchActive = branch.id === 'clarify' && clarificationActive;
            return (
              <button
                key={branch.id}
                type="button"
                onClick={() => onSelect(branch.parent)}
                className={`absolute z-10 -translate-x-1/2 -translate-y-1/2 rounded-xl border px-3 py-2 text-left focus-ring transition-all ${
                  branchActive
                    ? `${TONE_CLASSES[branch.tone]} shadow-card route-pulse`
                    : 'border-border-dim bg-abyss/90 text-ink-muted hover:border-border-base'
                }`}
                style={{ left: branch.x, top: branch.y }}
              >
                <span className="block text-[8px] font-mono font-bold uppercase tracking-[0.1em]">
                  {branch.label}
                </span>
                <span className="block text-[7px] mt-0.5 opacity-70">{branch.detail}</span>
              </button>
            );
          })}

          <div className="absolute z-10 left-[505px] top-[272px] -translate-x-1/2 flex gap-1.5">
            {SOURCE_CHIPS.map((source) => (
              <span
                key={source.label}
                className={`rounded-full border px-2 py-1 text-[7px] font-mono font-bold ${TONE_CLASSES[source.tone]}`}
              >
                {source.label}
              </span>
            ))}
          </div>

          <div className="absolute z-10 left-[655px] top-[249px] -translate-x-1/2 grid grid-cols-2 gap-1.5">
            {PLAN_CHIPS.map((plan) => (
              <button
                key={plan.label}
                type="button"
                onClick={() => onSelect('optimize')}
                className={`rounded-full border px-2.5 py-1 text-[7px] font-mono font-bold focus-ring ${TONE_CLASSES[plan.tone]}`}
                aria-label={`Inspect ${plan.label} plan branch`}
              >
                {plan.label}
              </button>
            ))}
          </div>

          <div className="absolute left-[20px] bottom-3 flex items-center gap-3 text-[7px] font-mono uppercase text-ink-ghost">
            <span className="flex items-center gap-1.5">
              <span className="w-1.5 h-1.5 rounded-full bg-ops-cyan" /> recorded
            </span>
            <span className="flex items-center gap-1.5">
              <span className="w-1.5 h-1.5 rounded-full bg-ops-amber" /> active
            </span>
            <span className="flex items-center gap-1.5">
              <span className="w-1.5 h-1.5 rounded-full bg-ops-rose" /> alternate stop
            </span>
          </div>
        </div>
      </div>
    </nav>
  );
}
