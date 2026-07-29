import { useCallback, useEffect, useMemo, useState } from 'react';
import type { RunEvent } from '../types/api';

interface GuidedPlaybackOptions {
  minimumDwellMs?: number;
  resetKey?: string;
}

export interface GuidedPlayback {
  visibleEvents: RunEvent[];
  revealedCount: number;
  totalCount: number;
  bufferedCount: number;
  isPaused: boolean;
  isCaughtUp: boolean;
  prefersReducedMotion: boolean;
  effectiveDwellMs: number;
  togglePaused: () => void;
  revealNext: () => void;
  revealLatest: () => void;
}

function readReducedMotionPreference(): boolean {
  return typeof window !== 'undefined'
    && window.matchMedia('(prefers-reduced-motion: reduce)').matches;
}

export function useGuidedPlayback(
  events: RunEvent[],
  options: GuidedPlaybackOptions = {},
): GuidedPlayback {
  const { minimumDwellMs = 1_800, resetKey = 'default' } = options;
  const [revealedCount, setRevealedCount] = useState(0);
  const [isPaused, setIsPaused] = useState(false);
  const [prefersReducedMotion, setPrefersReducedMotion] = useState(
    readReducedMotionPreference,
  );
  const effectiveDwellMs = prefersReducedMotion
    ? Math.min(minimumDwellMs, 450)
    : minimumDwellMs;

  useEffect(() => {
    const query = window.matchMedia('(prefers-reduced-motion: reduce)');
    const updatePreference = () => setPrefersReducedMotion(query.matches);
    updatePreference();
    query.addEventListener('change', updatePreference);
    return () => query.removeEventListener('change', updatePreference);
  }, []);

  useEffect(() => {
    setRevealedCount(0);
    setIsPaused(false);
  }, [resetKey]);

  useEffect(() => {
    if (events.length > 0 && revealedCount === 0) {
      setRevealedCount(1);
    }
  }, [events.length, revealedCount]);

  useEffect(() => {
    if (isPaused || revealedCount === 0 || revealedCount >= events.length) {
      return;
    }
    const timer = window.setTimeout(() => {
      setRevealedCount((current) => Math.min(current + 1, events.length));
    }, effectiveDwellMs);
    return () => window.clearTimeout(timer);
  }, [effectiveDwellMs, events.length, isPaused, revealedCount]);

  useEffect(() => {
    setRevealedCount((current) => Math.min(current, events.length));
  }, [events.length]);

  const revealNext = useCallback(() => {
    setRevealedCount((current) => Math.min(current + 1, events.length));
  }, [events.length]);

  const revealLatest = useCallback(() => {
    setRevealedCount(events.length);
    setIsPaused(false);
  }, [events.length]);

  const togglePaused = useCallback(() => {
    setIsPaused((current) => !current);
  }, []);

  const visibleEvents = useMemo(
    () => events.slice(0, revealedCount),
    [events, revealedCount],
  );
  const bufferedCount = Math.max(events.length - revealedCount, 0);

  return {
    visibleEvents,
    revealedCount,
    totalCount: events.length,
    bufferedCount,
    isPaused,
    isCaughtUp: events.length > 0 && bufferedCount === 0,
    prefersReducedMotion,
    effectiveDwellMs,
    togglePaused,
    revealNext,
    revealLatest,
  };
}
