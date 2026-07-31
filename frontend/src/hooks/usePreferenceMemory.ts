import { useCallback, useEffect, useRef, useState } from 'react';
import { api } from '../api/client';
import type { PreferenceSummary } from '../types/api';

interface UsePreferenceMemoryResult {
  data: PreferenceSummary | null;
  error: string | null;
  loading: boolean;
  refreshing: boolean;
  refresh: () => Promise<void>;
}

export function usePreferenceMemory(
  pollIntervalMs = 3_000,
): UsePreferenceMemoryResult {
  const [data, setData] = useState<PreferenceSummary | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [loading, setLoading] = useState(true);
  const [refreshing, setRefreshing] = useState(false);
  const mountedRef = useRef(true);
  const requestInFlightRef = useRef(false);

  const refresh = useCallback(async () => {
    if (requestInFlightRef.current) return;
    requestInFlightRef.current = true;
    setRefreshing(true);
    try {
      const summary = await api.getPreferenceSummary(6);
      if (!mountedRef.current) return;
      setData(summary);
      setError(null);
    } catch (caught: unknown) {
      if (!mountedRef.current) return;
      setError(
        caught instanceof Error
          ? caught.message
          : 'Preference memory is temporarily unavailable.',
      );
    } finally {
      requestInFlightRef.current = false;
      if (mountedRef.current) {
        setLoading(false);
        setRefreshing(false);
      }
    }
  }, []);

  useEffect(() => {
    mountedRef.current = true;
    void refresh();
    const timer = window.setInterval(() => {
      void refresh();
    }, pollIntervalMs);

    return () => {
      mountedRef.current = false;
      window.clearInterval(timer);
    };
  }, [pollIntervalMs, refresh]);

  return { data, error, loading, refreshing, refresh };
}
