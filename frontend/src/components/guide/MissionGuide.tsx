import type { RunStatus } from '../../types/api';
import {
  getActiveGuide,
  PHASE_TIMELINE,
  type PhaseGuide,
} from '../../data/guideContent';

interface MissionGuideProps {
  status: RunStatus | null;
  currentNode: string | null;
}

const PHASE_ORDER_ID: Record<string, number> = {
  receive: 0, interpret: 1, validate: 2, evidence: 3,
  optimize: 4, approval: 5, executing: 6, complete: 7, failed: 7,
};

function getPhaseIndexFromGuide(guide: PhaseGuide): number {
  return PHASE_ORDER_ID[guide.id] ?? 0;
}

function PhaseRow({
  phase,
  state,
}: {
  phase: { id: string; label: string; icon: string };
  state: 'done' | 'active' | 'pending' | 'failed';
}) {
  const base = 'flex items-center gap-3 py-2 px-3 rounded-lg transition-all duration-300';

  if (state === 'active') {
    return (
      <div className={`${base} bg-ops-amber/10 border border-ops-amber/30`}>
        <div className="relative w-5 h-5 shrink-0">
          <div className="w-5 h-5 rounded-full bg-ops-amber flex items-center justify-center text-void text-xs font-bold">
            <span className="animate-spin-slow">⟳</span>
          </div>
        </div>
        <span className="text-xs font-mono text-ops-amber-bright font-semibold">{phase.label}</span>
      </div>
    );
  }
  if (state === 'done') {
    return (
      <div className={`${base} opacity-60`}>
        <div className="w-5 h-5 rounded-full bg-ops-emerald/20 border border-ops-emerald/40 flex items-center justify-center text-ops-emerald text-xs shrink-0">
          ✓
        </div>
        <span className="text-xs font-mono text-ink-secondary line-through">{phase.label}</span>
      </div>
    );
  }
  if (state === 'failed') {
    return (
      <div className={`${base} bg-ops-rose/10 border border-ops-rose/30`}>
        <div className="w-5 h-5 rounded-full bg-ops-rose/20 border border-ops-rose/40 flex items-center justify-center text-ops-rose text-xs shrink-0">✗</div>
        <span className="text-xs font-mono text-ops-rose">{phase.label}</span>
      </div>
    );
  }
  return (
    <div className={`${base} opacity-40`}>
      <div className="w-5 h-5 rounded-full border border-border-base flex items-center justify-center text-ink-muted text-xs shrink-0">
        {phase.icon}
      </div>
      <span className="text-xs font-mono text-ink-muted">{phase.label}</span>
    </div>
  );
}

export function MissionGuide({ status, currentNode }: MissionGuideProps) {
  const guide = getActiveGuide(status, currentNode);
  const activeIndex = getPhaseIndexFromGuide(guide);
  const isFailed = status === 'FAILED';

  return (
    <aside className="w-full h-full bg-abyss border-l border-border-dim flex flex-col overflow-y-auto">
      {/* ── Header ─────────────────────────────────────────────── */}
      <div className="px-5 pt-5 pb-4 border-b border-border-dim shrink-0">
        <div className="flex items-center gap-2 mb-1">
          <div className="w-1.5 h-1.5 rounded-full bg-ops-amber animate-pulse-amber" />
          <span className="text-xs font-mono text-ops-amber uppercase tracking-widest font-semibold">
            Mission Guide
          </span>
        </div>
        <p className="text-xs text-ink-muted leading-relaxed">
          Real-time walkthrough of every agent phase. Expand each section to understand what's happening and what decisions you need to make.
        </p>
      </div>

      {/* ── Phase timeline ─────────────────────────────────────── */}
      <div className="px-3 py-4 border-b border-border-dim space-y-1 shrink-0">
        <p className="text-xs font-mono text-ink-muted uppercase tracking-widest mb-3 px-2">
          Agent Lifecycle
        </p>
        {PHASE_TIMELINE.map((phase, i) => {
          let state: 'done' | 'active' | 'pending' | 'failed' = 'pending';
          if (isFailed && i === activeIndex) state = 'failed';
          else if (i < activeIndex) state = 'done';
          else if (i === activeIndex) state = 'active';
          return <PhaseRow key={phase.id} phase={phase} state={state} />;
        })}
      </div>

      {/* ── Active guide panel ─────────────────────────────────── */}
      <div className="flex-1 px-5 py-5 space-y-5 overflow-y-auto">
        {/* Phase label */}
        <div className="flex items-center gap-2">
          <span className="text-lg">{guide.icon}</span>
          <h3 className="font-semibold text-sm text-ink-primary">{guide.label}</h3>
        </div>

        {/* What's happening */}
        <GuideSection title="What's Happening" color="cyan">
          {guide.whatIsHappening}
        </GuideSection>

        {/* Why it matters */}
        <GuideSection title="Why It Matters" color="amber">
          {guide.whyItMatters}
        </GuideSection>

        {/* What to watch */}
        <GuideSection title="What to Watch" color="violet">
          {guide.whatToWatch}
        </GuideSection>

        {/* Action prompt — only when manager needs to act */}
        {guide.actionPrompt && (
          <div className="rounded-lg border border-ops-amber/40 bg-ops-amber/8 p-4">
            <p className="text-xs font-mono text-ops-amber uppercase tracking-widest mb-2 font-semibold">
              ▶ Your Action Required
            </p>
            <p className="text-sm text-ops-amber-bright leading-relaxed">
              {guide.actionPrompt}
            </p>
          </div>
        )}

        {/* Key concept */}
        <div className="rounded-lg border border-border-dim bg-deep p-4 space-y-2">
          <p className="text-xs font-mono text-ink-muted uppercase tracking-widest">
            Key Concept
          </p>
          <p className="text-xs font-semibold text-ops-cyan-bright font-mono">
            {guide.keyConcept.term}
          </p>
          <p className="text-xs text-ink-secondary leading-relaxed">
            {guide.keyConcept.definition}
          </p>
        </div>
      </div>
    </aside>
  );
}

function GuideSection({
  title,
  color,
  children,
}: {
  title: string;
  color: 'cyan' | 'amber' | 'violet';
  children: string;
}) {
  const colorMap = {
    cyan:   'text-ops-cyan',
    amber:  'text-ops-amber',
    violet: 'text-ops-violet',
  };

  return (
    <div className="space-y-1.5">
      <p className={`text-xs font-mono uppercase tracking-widest font-semibold ${colorMap[color]}`}>
        {title}
      </p>
      <p className="text-xs text-ink-secondary leading-relaxed">{children}</p>
    </div>
  );
}
