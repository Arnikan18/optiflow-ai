import { PHASE_TIMELINE } from '../../data/guideContent';

interface DecisionJourneyRailProps {
  activeId: string;
  selectedId: string | null;
  failed: boolean;
  onSelect: (stageId: string | null) => void;
}

const STAGE_ALIASES: Record<string, string> = {
  clarify: 'validate',
  failed: 'complete',
};

const STAGE_SUMMARY: Record<string, string> = {
  receive: 'Open an auditable route',
  interpret: 'Structure priority and limits',
  validate: 'Guard policy and ambiguity',
  evidence: 'Join live operational facts',
  optimize: 'Compare measurable tradeoffs',
  approval: 'Pause for your decision',
  executing: 'Apply each approved change',
  complete: 'Verify outcome and receipts',
};

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
    PHASE_TIMELINE.findIndex((phase) => phase.id === normalizedActiveId),
    0,
  );
  const journeyComplete = normalizedActiveId === 'complete' && !failed;
  const placedCount = journeyComplete ? PHASE_TIMELINE.length : activeIndex + 1;

  return (
    <nav aria-label="Decision journey" className="mt-2">
      <div className="flex flex-wrap items-end justify-between gap-3 mb-4">
        <div>
          <div className="flex items-center gap-2">
            <p className="text-[9px] font-mono font-semibold uppercase tracking-[0.18em] text-ink-muted">
              Living journey
            </p>
            <span className="rounded-full bg-ops-cyan/10 px-2 py-1 text-[8px] font-mono font-semibold text-ops-cyan">
              {placedCount}/{PHASE_TIMELINE.length} cards placed
            </span>
          </div>
          <p className="text-[10px] text-ink-muted mt-1.5">
            Each card arrives at a readable pace and remains available without interrupting the live route.
          </p>
        </div>
        {selectedId && selectedId !== normalizedActiveId && (
          <button
            type="button"
            onClick={() => onSelect(null)}
            className="text-[10px] font-semibold text-ops-amber hover:underline focus-ring rounded"
          >
            Return to the live card →
          </button>
        )}
      </div>

      <div className="overflow-x-auto pb-2 -mx-1 px-1">
        <div className="relative min-w-[1080px] grid grid-cols-8 gap-2.5">
          <div className="absolute left-[6.25%] right-[6.25%] top-7 h-0.5 bg-border-dim" />
          <div
            className="absolute left-[6.25%] top-7 h-0.5 bg-ops-cyan transition-[width] duration-700"
            style={{
              width: `${activeIndex === 0 ? 0 : (activeIndex / 7) * 87.5}%`,
            }}
          />

          {PHASE_TIMELINE.map((phase, index) => {
            const placed = index <= activeIndex || journeyComplete;
            const done = index < activeIndex || journeyComplete;
            const current = index === activeIndex && !journeyComplete;
            const selected = selectedId === phase.id
              || (!selectedId && phase.id === normalizedActiveId);
            const failedCurrent = failed && current;

            if (!placed) {
              return (
                <div
                  key={phase.id}
                  className="relative z-10 min-h-[138px] rounded-xl border border-dashed border-border-dim bg-deep/50 px-3 pt-3.5"
                  aria-label={`${phase.label}, waiting to be placed`}
                >
                  <div className="w-7 h-7 rounded-full border-2 border-border-base bg-abyss flex items-center justify-center text-[9px] font-mono text-ink-ghost">
                    {String(index + 1).padStart(2, '0')}
                  </div>
                  <p className="text-[9px] leading-tight font-bold text-ink-ghost mt-4">
                    {phase.label}
                  </p>
                  <p className="text-[8px] leading-relaxed text-ink-ghost mt-2">
                    Waiting for the previous card
                  </p>
                </div>
              );
            }

            return (
              <button
                key={phase.id}
                type="button"
                onClick={() => onSelect(phase.id === normalizedActiveId ? null : phase.id)}
                aria-pressed={selected}
                aria-label={`${phase.label}, ${failedCurrent ? 'stopped' : current ? 'current' : 'recorded'}`}
                className={`animate-fade-up relative z-10 min-h-[138px] rounded-xl border px-3 pt-3.5 pb-3 text-left transition-all focus-ring ${
                  selected
                    ? 'border-ops-amber bg-abyss shadow-card -translate-y-0.5'
                    : done
                      ? 'border-ops-cyan/30 bg-abyss hover:border-ops-cyan/50'
                      : 'border-ops-amber/40 bg-ops-amber/[0.045]'
                }`}
                style={{ opacity: 0 }}
              >
                <div className="flex items-center justify-between gap-2">
                  <span className={`w-7 h-7 rounded-full border-2 flex items-center justify-center text-[9px] font-mono font-bold ${
                    failedCurrent
                      ? 'border-ops-rose bg-ops-rose text-white'
                      : current
                        ? 'border-ops-amber bg-ops-amber text-white route-pulse'
                        : 'border-ops-cyan bg-ops-cyan text-white'
                  }`}>
                    {done ? '✓' : String(index + 1).padStart(2, '0')}
                  </span>
                  <span className={`text-[8px] font-mono font-semibold uppercase tracking-wider ${
                    failedCurrent
                      ? 'text-ops-rose'
                      : current
                        ? 'text-ops-amber'
                        : 'text-ops-cyan'
                  }`}>
                    {failedCurrent ? 'stopped' : current ? 'now' : 'recorded'}
                  </span>
                </div>
                <p className={`text-[10px] leading-tight font-bold mt-3 ${
                  selected ? 'text-ink-primary' : 'text-ink-secondary'
                }`}>
                  {phase.label}
                </p>
                <p className="text-[8px] leading-relaxed text-ink-muted mt-2">
                  {STAGE_SUMMARY[phase.id]}
                </p>
              </button>
            );
          })}
        </div>
      </div>
    </nav>
  );
}
