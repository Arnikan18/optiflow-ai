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

  return (
    <nav aria-label="Decision journey" className="mt-5">
      <div className="flex flex-wrap items-end justify-between gap-3 mb-3">
        <div>
          <p className="text-[9px] font-mono font-semibold uppercase tracking-[0.18em] text-ink-muted">
            Journey ledger
          </p>
          <p className="text-[10px] text-ink-muted mt-1">
            Select any station to inspect its briefing without interrupting the live route.
          </p>
        </div>
        {selectedId && selectedId !== normalizedActiveId && (
          <button
            type="button"
            onClick={() => onSelect(null)}
            className="text-[10px] font-semibold text-ops-amber hover:underline focus-ring rounded"
          >
            Return to current station →
          </button>
        )}
      </div>

      <div className="overflow-x-auto pb-2 -mx-1 px-1">
        <div className="relative min-w-[960px] grid grid-cols-8 gap-2">
          <div className="absolute left-[6.25%] right-[6.25%] top-8 h-px bg-border-base" />
          <div
            className="absolute left-[6.25%] top-8 h-px bg-ops-cyan transition-[width] duration-700"
            style={{
              width: `${activeIndex === 0 ? 0 : (activeIndex / 7) * 87.5}%`,
            }}
          />

          {PHASE_TIMELINE.map((phase, index) => {
            const done = index < activeIndex || journeyComplete;
            const current = index === activeIndex && !journeyComplete;
            const selected = selectedId === phase.id
              || (!selectedId && phase.id === normalizedActiveId);
            const failedCurrent = failed && current;

            return (
              <button
                key={phase.id}
                type="button"
                onClick={() => onSelect(phase.id === normalizedActiveId ? null : phase.id)}
                aria-pressed={selected}
                className={`relative z-10 min-w-0 rounded-xl border px-2.5 pt-3 pb-3 text-left transition-all focus-ring ${
                  selected
                    ? 'border-ops-amber bg-abyss shadow-card -translate-y-0.5'
                    : done
                      ? 'border-ops-cyan/25 bg-abyss hover:border-ops-cyan/50'
                      : current
                        ? 'border-ops-amber/40 bg-ops-amber/[0.045]'
                        : 'border-border-dim bg-deep hover:border-border-base'
                }`}
              >
                <div className="flex items-center justify-between gap-2">
                  <span className={`w-7 h-7 rounded-full border-2 flex items-center justify-center text-[9px] font-mono font-bold ${
                    failedCurrent
                      ? 'border-ops-rose bg-ops-rose text-white'
                      : current
                        ? 'border-ops-amber bg-ops-amber text-white route-pulse'
                        : done
                          ? 'border-ops-cyan bg-ops-cyan text-white'
                          : 'border-border-base bg-abyss text-ink-muted'
                  }`}>
                    {done ? '✓' : String(index + 1).padStart(2, '0')}
                  </span>
                  <span className={`text-[8px] font-mono font-semibold uppercase tracking-wider ${
                    failedCurrent
                      ? 'text-ops-rose'
                      : current
                        ? 'text-ops-amber'
                        : done
                          ? 'text-ops-cyan'
                          : 'text-ink-ghost'
                  }`}>
                    {failedCurrent ? 'stopped' : current ? 'now' : done ? 'recorded' : 'upcoming'}
                  </span>
                </div>
                <p className={`text-[10px] leading-tight font-bold mt-3 ${
                  selected ? 'text-ink-primary' : 'text-ink-secondary'
                }`}>
                  {phase.label}
                </p>
                <p className="text-[8px] font-mono text-ink-ghost mt-1.5">
                  Station {String(index + 1).padStart(2, '0')}
                </p>
              </button>
            );
          })}
        </div>
      </div>
    </nav>
  );
}
