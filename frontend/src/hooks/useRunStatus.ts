import { useState, useEffect, useCallback } from 'react';
import { api } from '../api/client';
import type { RunSummary } from '../types/api';

const TERMINAL_STATUSES = new Set(['COMPLETED', 'FAILED']);
const POLL_INTERVAL_MS = 3000;

/**
 * Polls GET /api/v1/runs/{runId} every 3 seconds until the run
 * reaches a terminal status (COMPLETED / FAILED).
 * Also used as the fallback when the SSE stream fails.
 */
export function useRunStatus(runId: string | undefined) {
  const [data, setData] = useState<RunSummary | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [loading, setLoading] = useState(true);

  const fetch = useCallback(async () => {
    if (!runId) return;
    try {
      const result = await api.getRunStatus(runId);
      setData(result);
      setError(null);
    } catch (err: unknown) {
      const msg = err instanceof Error ? err.message : 'Failed to fetch run status';
      setError(msg);
    } finally {
      setLoading(false);
    }
  }, [runId]);

  useEffect(() => {
    if (!runId) return;

    setData(null);
    setError(null);
    setLoading(true);

    fetch();

    const interval = setInterval(() => {
      if (data && TERMINAL_STATUSES.has(data.status)) {
        clearInterval(interval);
        return;
      }
      fetch();
    }, POLL_INTERVAL_MS);

    return () => clearInterval(interval);
  }, [runId, fetch]); // eslint-disable-line react-hooks/exhaustive-deps

  return { data, error, loading, refetch: fetch };
}
