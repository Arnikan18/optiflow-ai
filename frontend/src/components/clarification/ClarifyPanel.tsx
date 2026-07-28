import { useState } from 'react';
import { api } from '../../api/client';
import type { RunSummary } from '../../types/api';

interface ClarifyPanelProps {
  runId: string;
  runData: RunSummary | null;
  onSubmitted: () => void;
}

export function ClarifyPanel({ runId, runData, onSubmitted }: ClarifyPanelProps) {
  const [reply, setReply] = useState('');
  const [submitting, setSubmitting] = useState(false);
  const [error, setError] = useState<string | null>(null);

  // Try to extract clarification context from the checkpoint (may be in candidate_plans fallback)
  const ambiguities: string[] =
    (runData as unknown as { structured_goal?: { ambiguities?: string[] } })
      ?.structured_goal?.ambiguities ?? [];

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    const trimmed = reply.trim();
    if (!trimmed) return;

    setSubmitting(true);
    setError(null);
    try {
      await api.clarifyRun(runId, { clarification_reply: trimmed });
      onSubmitted();
    } catch (err: unknown) {
      const msg = err instanceof Error ? err.message : 'Failed to submit clarification';
      setError(msg);
      setSubmitting(false);
    }
  };

  return (
    <div className="animate-scale-in max-w-2xl mx-auto space-y-6">
      {/* Header */}
      <div className="flex items-start gap-4 p-5 bg-ops-orange/8 border border-ops-orange/30 rounded-xl">
        <span className="text-3xl shrink-0">❓</span>
        <div className="space-y-1">
          <h2 className="text-base font-bold text-ink-primary">Clarification Required</h2>
          <p className="text-sm text-ink-secondary leading-relaxed">
            The goal validator found an ambiguity it cannot resolve automatically. Provide a specific answer below to resume execution. Your response will be recorded in the permanent audit trail.
          </p>
        </div>
      </div>

      {/* What was ambiguous */}
      <div className="bg-deep border border-border-dim rounded-xl p-5 space-y-3">
        <p className="text-xs font-mono text-ops-orange uppercase tracking-widest font-semibold">
          Ambiguities Detected
        </p>
        {ambiguities.length > 0 ? (
          <ul className="space-y-2">
            {ambiguities.map((a, i) => (
              <li key={i} className="flex items-start gap-3 text-sm text-ink-secondary">
                <span className="text-ops-orange font-mono shrink-0">{i + 1}.</span>
                <span>{a}</span>
              </li>
            ))}
          </ul>
        ) : (
          <p className="text-sm text-ink-secondary">
            The system requires additional context to proceed. Please describe your priority rules, constraint preferences, or any special considerations that should guide the allocation.
          </p>
        )}
      </div>

      {/* Decision guidance */}
      <div className="grid grid-cols-1 sm:grid-cols-3 gap-3">
        {[
          { label: 'Be specific', tip: 'Vague answers may cause another clarification loop.' },
          { label: 'State priorities', tip: 'Tell the system which tier, metric, or constraint matters most.' },
          { label: 'Plain English', tip: 'No technical jargon needed — the AI interprets natural language.' },
        ].map(({ label, tip }) => (
          <div key={label} className="bg-abyss border border-border-dim rounded-lg p-3">
            <p className="text-xs font-semibold text-ink-primary mb-1">{label}</p>
            <p className="text-xs text-ink-muted leading-relaxed">{tip}</p>
          </div>
        ))}
      </div>

      {/* Reply form */}
      <form onSubmit={handleSubmit} className="space-y-4">
        <div>
          <label className="text-xs font-mono text-ink-secondary uppercase tracking-widest block mb-2">
            Your Response
          </label>
          <textarea
            value={reply}
            onChange={(e) => setReply(e.target.value)}
            rows={4}
            disabled={submitting}
            placeholder="e.g. 'Prioritise Tier 1 customers over Tier 2 when specialist capacity is full. Assign at least one specialist to any incident with an SLA breach within 4 hours.'"
            className="w-full bg-deep border border-border-dim rounded-lg p-4 text-ink-primary
              placeholder:text-ink-ghost resize-none focus:outline-none focus:border-ops-orange
              font-sans text-sm leading-relaxed transition-colors disabled:opacity-50"
          />
        </div>

        {error && (
          <div className="border border-ops-rose/40 bg-ops-rose/8 rounded-lg px-4 py-3 text-sm text-ops-rose">
            ✗ {error}
          </div>
        )}

        <button
          type="submit"
          disabled={submitting || reply.trim().length < 5}
          className="w-full bg-ops-orange text-void font-bold py-3.5 rounded-lg uppercase tracking-widest
            text-sm hover:brightness-110 disabled:opacity-30 disabled:cursor-not-allowed
            transition-all duration-200 flex items-center justify-center gap-3"
        >
          {submitting ? (
            <>
              <span className="w-4 h-4 border-2 border-void/30 border-t-void rounded-full animate-spin" />
              Resuming Execution…
            </>
          ) : (
            'Submit & Resume →'
          )}
        </button>
      </form>
    </div>
  );
}
