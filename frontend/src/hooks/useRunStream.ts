import { useEffect, useRef, useState } from 'react';
import type { RunEvent } from '../types/api';

interface UseRunStreamResult {
  events: RunEvent[];
  connected: boolean;
  usingFallback: boolean;
}

type StreamEvent = Omit<RunEvent, 'event_id'> & {
  event_id?: string;
};

function normalizeEvent(event: StreamEvent, runId: string): RunEvent {
  return {
    ...event,
    event_id: event.event_id
      ?? `${runId}:${event.sequence_number}:${event.event_type}:${event.state_version ?? 'none'}`,
    received_at: new Date().toISOString(),
  };
}

/**
 * Opens the named `run_event` SSE stream and retains historical events.
 * Historical payloads currently omit event_id, so a deterministic client ID
 * is derived from immutable event fields for rendering and de-duplication.
 */
export function useRunStream(runId: string | undefined): UseRunStreamResult {
  const [events, setEvents] = useState<RunEvent[]>([]);
  const [connected, setConnected] = useState(false);
  const [usingFallback, setUsingFallback] = useState(false);
  const sourceRef = useRef<EventSource | null>(null);

  useEffect(() => {
    if (!runId) return;

    setEvents([]);
    setConnected(false);
    setUsingFallback(false);

    let source: EventSource;
    try {
      source = new EventSource(`/api/v1/runs/${encodeURIComponent(runId)}/stream`);
      sourceRef.current = source;

      source.onopen = () => {
        setConnected(true);
        setUsingFallback(false);
      };

      const handleEvent = (message: MessageEvent<string>) => {
        try {
          const event = normalizeEvent(JSON.parse(message.data) as StreamEvent, runId);
          setEvents((previous) => {
            if (previous.some((item) => item.event_id === event.event_id)) {
              return previous;
            }
            return [...previous, event].sort(
              (left, right) => left.sequence_number - right.sequence_number,
            );
          });
        } catch {
          // Ignore malformed payloads; the status poll remains available.
        }
      };

      source.addEventListener('run_event', handleEvent as EventListener);
      source.onmessage = handleEvent;

      source.onerror = () => {
        setConnected(false);
        setUsingFallback(true);
        source.close();
      };

      return () => {
        source.removeEventListener('run_event', handleEvent as EventListener);
        source.close();
        sourceRef.current = null;
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
