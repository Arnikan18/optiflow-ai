import { useState, useEffect, useRef } from 'react';
import type { RunEvent } from '../types/api';

interface UseRunStreamResult {
  events: RunEvent[];
  connected: boolean;
  usingFallback: boolean;
}

/**
 * Opens an SSE EventSource connection to /api/v1/runs/{runId}/stream.
 * If the connection fails, signals usingFallback so the caller can
 * rely on the useRunStatus polling hook instead.
 */
export function useRunStream(runId: string | undefined): UseRunStreamResult {
  const [events, setEvents] = useState<RunEvent[]>([]);
  const [connected, setConnected] = useState(false);
  const [usingFallback, setUsingFallback] = useState(false);
  const sourceRef = useRef<EventSource | null>(null);

  useEffect(() => {
    if (!runId) return;

    // Reset when runId changes
    setEvents([]);
    setConnected(false);
    setUsingFallback(false);

    let source: EventSource;
    try {
      source = new EventSource(`/api/v1/runs/${runId}/stream`);
      sourceRef.current = source;

      source.onopen = () => {
        setConnected(true);
        setUsingFallback(false);
      };

      source.onmessage = (e: MessageEvent) => {
        try {
          const event = JSON.parse(e.data) as RunEvent;
          event.received_at = new Date().toISOString();
          setEvents((prev) => {
            // Deduplicate by event_id
            if (prev.some((p) => p.event_id === event.event_id)) return prev;
            return [...prev, event];
          });
        } catch {
          // Malformed SSE payload — ignore
        }
      };

      source.onerror = () => {
        setConnected(false);
        setUsingFallback(true);
        source.close();
      };
    } catch {
      setUsingFallback(true);
    }

    return () => {
      sourceRef.current?.close();
      sourceRef.current = null;
    };
  }, [runId]);

  return { events, connected, usingFallback };
}
