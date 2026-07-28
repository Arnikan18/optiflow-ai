import type { RunStatus } from '../../types/api';
import { getActiveGuide } from '../../data/guideContent';

interface MissionGuideProps {
  status: RunStatus | null;
  currentNode: string | null;
}

const CHECKS_BY_PHASE: Record<string, string[]> = {
  receive: ['Goal saved', 'Run ID assigned', 'Audit record opened'],
  interpret: ['Primary objective', 'Hard constraints', 'Time horizon'],
  validate: ['Policy conflicts', 'Missing priorities', 'Unsafe assumptions'],
  clarify: ['Ambiguity resolved', 'Answer recorded', 'Policy fit restored'],
  evidence: ['Customer impact', 'SLA urgency', 'Skills and capacity', 'Data freshness'],
  optimize: ['Hard constraints', 'Coverage and ARR', 'Workload fairness', 'Alternative trade-offs'],
  approval: ['Recommendation evidence', 'Trade-offs', 'Unassigned work', 'Your explicit approval'],
  executing: ['Capacity reserved', 'Incident assigned', 'Notification delivered', 'Receipt confirmed'],
  complete: ['Every write confirmed', 'Final metrics captured', 'Audit trail closed'],
  failed: ['Partial writes rolled back', 'Failure point recorded', 'Systems left consistent'],
};

const MANUAL_MOVE: Record<string, string> = {
  receive: 'Write down the goal, owner, time, and a unique reference.',
  interpret: 'Underline the priority, circle every limit, and write the decision timeframe.',
  validate: 'Ask whether the goal breaks policy or leaves a critical choice unspecified.',
  clarify: 'Get a precise answer from the decision owner before collecting evidence.',
  evidence: 'Compare customer value, SLA deadline, required skill, and current capacity.',
  optimize: 'Create at least two viable assignments and state the cost of each one.',
  approval: 'Choose the trade-off you accept and record who authorised it.',
  executing: 'Apply one change at a time and verify it before continuing.',
  complete: 'Record what changed, who was notified, and any work left unassigned.',
  failed: 'Stop, reverse partial changes, and document the exact failure point.',
};

function GuideSection({
  marker,
  title,
  children,
}: {
  marker: string;
  title: string;
  children: React.ReactNode;
}) {
  return (
    <section className="px-5 py-5 border-b border-border-dim last:border-b-0">
      <div className="flex items-center gap-2 mb-2.5">
        <span className="text-[9px] font-mono font-semibold text-ops-amber">{marker}</span>
        <h3 className="text-[9px] font-mono font-semibold uppercase tracking-[0.17em] text-ink-muted">{title}</h3>
      </div>
      {children}
    </section>
  );
}

export function MissionGuide({ status, currentNode }: MissionGuideProps) {
  const guide = getActiveGuide(status, currentNode);
  const checks = CHECKS_BY_PHASE[guide.id] ?? [];

  return (
    <div className="w-full">
      <div className="px-5 py-5 bg-ink-primary text-white">
        <div className="flex items-center justify-between gap-3">
          <div>
            <p className="text-[9px] font-mono text-[#ff8a64] uppercase tracking-[0.18em] font-semibold">Step briefing</p>
            <h2 className="font-bold text-base mt-1">{guide.label}</h2>
          </div>
          <div className="w-9 h-9 rounded-full border border-white/15 flex items-center justify-center">
            <span className="w-2 h-2 rounded-full bg-[#ff8a64] animate-pulse" />
          </div>
        </div>
        <p className="text-xs text-white/60 leading-relaxed mt-4">
          Read this panel to follow the logic or repeat the step manually.
        </p>
      </div>

      <GuideSection marker="01" title="What is happening">
        <p className="text-xs text-ink-secondary leading-relaxed">{guide.whatIsHappening}</p>
      </GuideSection>

      <GuideSection marker="02" title="Checks in this step">
        <ul className="space-y-2.5">
          {checks.map((check, index) => (
            <li key={check} className="flex items-center gap-3">
              <span className={`w-5 h-5 rounded-full flex items-center justify-center text-[9px] ${
                index === 0 ? 'bg-ops-cyan text-white' : 'bg-deep border border-border-dim text-ink-muted'
              }`}>
                {index === 0 ? '✓' : index + 1}
              </span>
              <span className="text-xs font-semibold text-ink-secondary">{check}</span>
            </li>
          ))}
        </ul>
      </GuideSection>

      <GuideSection marker="03" title="Why it matters">
        <p className="text-xs text-ink-secondary leading-relaxed">{guide.whyItMatters}</p>
      </GuideSection>

      <GuideSection marker="04" title="If you did this manually">
        <div className="rounded-xl bg-deep border border-border-dim p-4">
          <p className="text-xs text-ink-primary font-semibold leading-relaxed">{MANUAL_MOVE[guide.id]}</p>
        </div>
      </GuideSection>

      {guide.actionPrompt && (
        <section className="m-4 rounded-xl bg-ops-amber text-white p-4 shadow-amber-glow">
          <p className="text-[9px] font-mono font-semibold uppercase tracking-[0.16em] text-white/70">Your move</p>
          <p className="text-xs font-semibold leading-relaxed mt-2">{guide.actionPrompt}</p>
        </section>
      )}

      <div className="px-5 py-4 bg-deep border-t border-border-dim">
        <div className="flex gap-3">
          <span className="text-ops-cyan text-sm">i</span>
          <div>
            <p className="text-[9px] font-mono uppercase tracking-[0.14em] text-ink-muted">{guide.keyConcept.term}</p>
            <p className="text-[11px] leading-relaxed text-ink-secondary mt-1.5">{guide.keyConcept.definition}</p>
          </div>
        </div>
      </div>
    </div>
  );
}
