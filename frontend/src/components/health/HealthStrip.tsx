import { useCallback, useEffect, useState } from 'react';
import { api } from '../../api/client';
import type { DemoHealth, HealthComponent } from '../../types/api';

const COMPONENT_LABELS: Record<string, string> = {
  'core-api': 'Core',
  postgres: 'Data',
  crm: 'CRM',
  incident: 'Incident',
  workforce: 'Workforce',
  communication: 'Comms',
};

const STATUS_DOT = {
  HEALTHY: 'bg-ops-emerald',
  DEGRADED: 'bg-ops-orange',
  UNHEALTHY: 'bg-ops-rose',
} as const;

function componentLabel(component: HealthComponent): string {
  return COMPONENT_LABELS[component.name.toLowerCase()] ?? component.name;
}

export function HealthStrip() {
  const [health, setHealth] = useState<DemoHealth | null>(null);
  const [checking, setChecking] = useState(true);
  const [error, setError] = useState(false);

  const checkHealth = useCallback(async () => {
    setChecking(true);
    try {
      setHealth(await api.getDemoHealth());
      setError(false);
    } catch {
      setError(true);
    } finally {
      setChecking(false);
    }
  }, []);

  useEffect(() => {
    void checkHealth();
    const timer = window.setInterval(() => void checkHealth(), 30_000);
    return () => window.clearInterval(timer);
  }, [checkHealth]);

  const components = health?.components ?? [];
  const readyCount = components.filter((component) => component.status === 'HEALTHY').length;
  const isHealthy = health?.overall_status === 'HEALTHY';
  const networkDot = checking && !health
    ? 'bg-ink-muted'
    : error || health?.overall_status === 'UNHEALTHY'
      ? 'bg-ops-rose'
      : isHealthy
        ? 'bg-ops-emerald'
        : 'bg-ops-orange';

  return (
    <div className="bg-ink-primary text-white px-5 sm:px-8 py-2.5 flex items-center gap-5 overflow-x-auto">
      <div className="flex items-center gap-2.5 shrink-0">
        <span className="relative flex w-2 h-2">
          <span className={`absolute inset-0 rounded-full ${networkDot} animate-ping opacity-40`} />
          <span className={`relative w-2 h-2 rounded-full ${networkDot}`} />
        </span>
        <span className="text-[9px] font-mono text-white/50 uppercase tracking-[0.16em]">
          Evidence network
        </span>
        <span className="text-[9px] font-mono font-semibold text-white">
          {error
            ? 'check unavailable'
            : checking && !health
              ? 'checking'
              : `${readyCount}/${components.length} ready`}
        </span>
      </div>

      <div className="h-4 w-px bg-white/15 shrink-0" />

      <div className="flex items-center gap-4">
        {components.length === 0 && !error && (
          <span className="text-[9px] font-mono uppercase tracking-wider text-white/40">
            Reading source status…
          </span>
        )}
        {components.map((component) => (
          <div key={component.name} className="flex items-center gap-1.5 shrink-0">
            <span className={`w-1.5 h-1.5 rounded-full ${STATUS_DOT[component.status]}`} />
            <span className="text-[9px] font-mono text-white/60 uppercase tracking-wider">
              {componentLabel(component)}
            </span>
            {component.latency_ms !== null && (
              <span className="text-[9px] text-white/30 font-mono hidden xl:block">
                {Math.round(component.latency_ms)}ms
              </span>
            )}
          </div>
        ))}
      </div>

      <div className="ml-auto shrink-0 hidden md:flex items-center gap-3">
        {health?.checked_at && (
          <span className="text-[9px] font-mono text-white/30">
            checked {new Date(health.checked_at).toLocaleTimeString()}
          </span>
        )}
        <button
          type="button"
          onClick={() => void checkHealth()}
          disabled={checking}
          className="text-[9px] font-mono text-white/60 hover:text-white disabled:opacity-40 transition-colors uppercase tracking-[0.15em] focus-ring rounded"
        >
          {checking ? 'Checking' : 'Refresh'}
        </button>
      </div>
    </div>
  );
}
