import { useEffect, useState } from 'react';
import type { RunEvent, RunStatus } from '../../types/api';
import { getActiveGuide } from '../../data/guideContent';
import { readUiPreferences, subscribeToUiPreferences } from '../../preferences';

interface MissionGuideProps {
  status: RunStatus | null;
  currentNode: string | null;
  events: RunEvent[];
  isReviewing: boolean;
}

const CHECKS_BY_PHASE: Record<string, string[]> = {
  receive: ['Goal saved', 'Run ID assigned', 'Audit record opened'],
  interpret: ['Primary objective', 'Hard constraints', 'Time horizon'],
  validate: ['Policy conflicts', 'Missing priorities', 'Unsafe assumptions'],
  clarify: ['Ambiguity resolved', 'Answer recorded', 'Policy fit restored'],
  evidence: ['Customer impact', 'SLA urgency', 'Skills and capacity', 'Data freshness'],
  optimize: ['Hard constraints', 'Coverage and ARR', 'Workload fairness', 'Alternative tradeoffs'],
  approval: ['Recommendation evidence', 'Tradeoffs', 'Unassigned work', 'Explicit approval'],
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
  approval: 'Choose the tradeoff you accept and record who authorised it.',
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
        <h3 className="text-[9px] font-mono font-semibold uppercase tracking-[0.17em] text-ink-muted">
          {title}
        </h3>
      </div>
      {children}
    </section>
  );
}

function formatRecordedTime(event: RunEvent | undefined): string {
  if (!event?.received_at) return 'Backend timestamp not supplied';
  return new Date(event.received_at).toLocaleTimeString([], {
    hour: '2-digit',
    minute: '2-digit',
    second: '2-digit',
  });
}

export function MissionGuide({
  status,
  currentNode,
  events,
  isReviewing,
}: MissionGuideProps) {
  const [preferences, setPreferences] = useState(readUiPreferences);
  const guide = getActiveGuide(status, currentNode);
  const compact = preferences.detail === 'compact';
  const checks = CHECKS_BY_PHASE[guide.id] ?? [];
  const latestEvent = events.at(-1);
  const inputFields = Array.from(
    new Set(events.flatMap((event) => Object.keys(event.payload ?? {}))),
  ).slice(0, 8);
  const sourceNodes = Array.from(new Set(events.map((event) => event.source)));

  useEffect(() => subscribeToUiPreferences(setPreferences), []);

  return (
    <div className="w-full">
      <div className="px-5 py-5 bg-ink-primary text-white">
        <div className="flex items-center justify-between gap-3">
          <div>
            <p className="text-[9px] font-mono text-[#ff8a64] uppercase tracking-[0.18em] font-semibold">
              {isReviewing ? 'Recorded step briefing' : 'Live step briefing'}
            </p>
            <h2 className="font-bold text-base mt-1">{guide.label}</h2>
          </div>
          <div className="w-9 h-9 rounded-full border border-white/15 flex items-center justify-center">
            <span className={`w-2 h-2 rounded-full bg-[#ff8a64] ${isReviewing ? '' : 'animate-pulse'}`} />
          </div>
        </div>
        <p className="text-xs text-white/60 leading-relaxed mt-4">
          {compact
            ? 'Compact briefing keeps the checks and recorded result in view.'
            : 'Follow the reasoning, inspect the evidence, or repeat this step manually.'}
        </p>
      </div>

      <GuideSection marker="01" title="What is happening">
        <p className="text-xs text-ink-secondary leading-relaxed">{guide.whatIsHappening}</p>
      </GuideSection>

      <GuideSection marker="02" title="Inputs and checks">
        <div className="grid grid-cols-2 gap-2 mb-4">
          <div className="rounded-lg bg-deep border border-border-dim p-3">
            <p className="text-[8px] font-mono uppercase tracking-[0.13em] text-ink-muted">Events used</p>
            <p className="text-lg font-extrabold text-ink-primary mt-1">{events.length}</p>
          </div>
          <div className="rounded-lg bg-deep border border-border-dim p-3">
            <p className="text-[8px] font-mono uppercase tracking-[0.13em] text-ink-muted">Source nodes</p>
            <p className="text-lg font-extrabold text-ink-primary mt-1">{sourceNodes.length}</p>
          </div>
        </div>
        <ul className="space-y-2.5">
          {checks.map((check) => (
            <li key={check} className="flex items-center gap-3">
              <span className="w-5 h-5 rounded-full bg-ops-cyan/10 text-ops-cyan flex items-center justify-center text-[9px]">
                ✓
              </span>
              <span className="text-xs font-semibold text-ink-secondary">{check}</span>
            </li>
          ))}
        </ul>
        {inputFields.length > 0 && (
          <div className="mt-4 pt-4 border-t border-border-dim">
            <p className="text-[8px] font-mono uppercase tracking-[0.14em] text-ink-muted mb-2">
              Payload fields supplied
            </p>
            <div className="flex flex-wrap gap-1.5">
              {inputFields.map((field) => (
                <code key={field} className="rounded bg-surface px-2 py-1 text-[9px] text-ink-secondary">
                  {field}
                </code>
              ))}
            </div>
          </div>
        )}
      </GuideSection>

      <GuideSection marker="03" title="Result and impact">
        <p className="text-xs font-semibold text-ink-primary leading-relaxed">
          {latestEvent?.summary ?? 'This step has not supplied a result summary yet.'}
        </p>
        <p className="text-xs text-ink-secondary leading-relaxed mt-3">{guide.whyItMatters}</p>
        <div className="rounded-xl border border-ops-cyan/25 bg-ops-cyan/5 p-3.5 mt-4">
          <p className="text-[8px] font-mono uppercase tracking-[0.14em] text-ops-cyan">What to verify</p>
          <p className="text-[11px] leading-relaxed text-ink-secondary mt-1.5">{guide.whatToWatch}</p>
        </div>
      </GuideSection>

      {!compact && <GuideSection marker="04" title="Timing truth">
        <div className="flex items-start justify-between gap-4">
          <div>
            <p className="text-[8px] font-mono uppercase tracking-[0.14em] text-ink-muted">Latest record</p>
            <p className="text-xs font-semibold text-ink-primary mt-1">
              {formatRecordedTime(latestEvent)}
            </p>
          </div>
          <span className="rounded-full bg-ops-amber/10 px-2 py-1 text-[8px] font-mono text-ops-amber">
            Presentation paced
          </span>
        </div>
        <p className="text-[10px] leading-relaxed text-ink-muted mt-3">
          Backend duration is shown only when the API supplies it. The guided card dwell is presentation time,
          added so the route remains readable.
        </p>
      </GuideSection>}

      {!compact && <GuideSection marker="05" title="If you did this manually">
        <div className="rounded-xl bg-deep border border-border-dim p-4">
          <p className="text-xs text-ink-primary font-semibold leading-relaxed">
            {MANUAL_MOVE[guide.id]}
          </p>
        </div>
      </GuideSection>}

      {!compact && <GuideSection marker="06" title="Raw event evidence">
        {events.length === 0 ? (
          <p className="text-[10px] leading-relaxed text-ink-muted">
            No event payload has been presented for this step yet.
          </p>
        ) : (
          <div className="space-y-2">
            {events.map((event) => (
              <details key={event.event_id} className="rounded-lg border border-border-dim bg-deep">
                <summary className="cursor-pointer px-3 py-2.5 text-[9px] font-mono font-semibold text-ink-secondary focus-ring rounded">
                  {event.event_type} · event {String(event.sequence_number).padStart(2, '0')}
                </summary>
                <pre className="max-h-56 overflow-auto border-t border-border-dim p-3 text-[9px] leading-relaxed text-ink-muted">
                  {JSON.stringify(event.payload ?? { note: 'No payload supplied' }, null, 2)}
                </pre>
              </details>
            ))}
          </div>
        )}
      </GuideSection>}

      {guide.actionPrompt && (
        <section className="m-4 rounded-xl bg-ops-amber text-white p-4 shadow-amber-glow">
          <p className="text-[9px] font-mono font-semibold uppercase tracking-[0.16em] text-white/70">
            Your move
          </p>
          <p className="text-xs font-semibold leading-relaxed mt-2">{guide.actionPrompt}</p>
        </section>
      )}

      {!compact && <div className="px-5 py-4 bg-deep border-t border-border-dim">
        <div className="flex gap-3">
          <span className="text-ops-cyan text-sm">i</span>
          <div>
            <p className="text-[9px] font-mono uppercase tracking-[0.14em] text-ink-muted">
              {guide.keyConcept.term}
            </p>
            <p className="text-[11px] leading-relaxed text-ink-secondary mt-1.5">
              {guide.keyConcept.definition}
            </p>
          </div>
        </div>
      </div>}
    </div>
  );
}
