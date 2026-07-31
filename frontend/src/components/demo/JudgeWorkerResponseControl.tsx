import { useState } from 'react';
import { api } from '../../api/client';
import type { DemoPortfolio, QueuedResponseStatus } from '../../types/api';

interface JudgeWorkerResponseControlProps {
  portfolio: DemoPortfolio | null;
}

export function JudgeWorkerResponseControl({
  portfolio,
}: JudgeWorkerResponseControlProps) {
  const [workerId, setWorkerId] = useState('');
  const [busy, setBusy] = useState<QueuedResponseStatus | null>(null);
  const [message, setMessage] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);

  const queueResponse = async (status: QueuedResponseStatus) => {
    setBusy(status);
    setMessage(null);
    setError(null);
    try {
      await api.queueSpecialistResponse({
        specialist_id: workerId || undefined,
        status,
        reason: status === 'ACCEPTED'
          ? 'Judge simulation: worker accepted the proposed work.'
          : 'Judge simulation: worker declined the proposed work.',
        response_delay_seconds: 2,
        apply_once: true,
        expires_after_seconds: 900,
      });
      const worker = portfolio?.specialists.find(
        (item) => item.specialist_id === workerId,
      );
      setMessage(
        `${worker?.specialist_name ?? 'The next matching worker'} will ${
          status === 'ACCEPTED' ? 'accept' : 'decline'
        } one assignment request.`,
      );
    } catch (caught: unknown) {
      setError(caught instanceof Error ? caught.message : 'The worker response could not be queued.');
    } finally {
      setBusy(null);
    }
  };

  return (
    <section className="rounded-[1.5rem] border border-border-dim bg-abyss p-5 shadow-card">
      <div className="flex flex-col gap-4 lg:flex-row lg:items-end lg:justify-between">
        <div>
          <p className="text-xs font-mono font-bold uppercase tracking-[0.14em] text-ops-violet">
            Next worker response
          </p>
          <h2 className="mt-1 text-xl font-extrabold text-ink-primary">
            Simulate accept or decline
          </h2>
          <p className="mt-1 text-sm text-ink-muted">
            The response is consumed once when an approved plan requests this worker.
          </p>
        </div>

        <div className="flex flex-col gap-2 sm:flex-row sm:items-end">
          <label className="min-w-56">
            <span className="text-xs font-bold text-ink-muted">Worker</span>
            <select
              value={workerId}
              onChange={(event) => setWorkerId(event.target.value)}
              disabled={busy !== null}
              className="mt-1 block min-h-11 w-full rounded-xl border border-border-base bg-deep px-3 py-2 text-sm font-bold text-ink-primary focus-ring"
            >
              <option value="">Any next worker</option>
              {(portfolio?.specialists ?? []).map((worker) => (
                <option key={worker.specialist_id} value={worker.specialist_id}>
                  {worker.specialist_name}
                </option>
              ))}
            </select>
          </label>
          <button
            type="button"
            disabled={busy !== null}
            onClick={() => void queueResponse('ACCEPTED')}
            className="min-h-11 rounded-xl bg-ops-emerald px-4 py-3 text-sm font-bold text-white disabled:opacity-40 focus-ring"
          >
            {busy === 'ACCEPTED' ? 'Queuing…' : 'Accept next'}
          </button>
          <button
            type="button"
            disabled={busy !== null}
            onClick={() => void queueResponse('REJECTED')}
            className="min-h-11 rounded-xl border border-ops-rose/40 bg-ops-rose/[0.06] px-4 py-3 text-sm font-bold text-ops-rose disabled:opacity-40 focus-ring"
          >
            {busy === 'REJECTED' ? 'Queuing…' : 'Decline next'}
          </button>
        </div>
      </div>

      {message && (
        <p className="mt-4 rounded-xl border border-ops-emerald/25 bg-ops-emerald/[0.06] px-4 py-3 text-sm font-bold text-ops-emerald" role="status">
          {message}
        </p>
      )}
      {error && (
        <p className="mt-4 rounded-xl border border-ops-rose/25 bg-ops-rose/[0.06] px-4 py-3 text-sm font-bold text-ops-rose" role="alert">
          {error}
        </p>
      )}
    </section>
  );
}
