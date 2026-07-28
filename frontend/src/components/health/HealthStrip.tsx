import { useEffect, useState } from 'react';
import type { ServiceHealth, ServiceHealthStatus } from '../../types/api';

const SERVICES: Omit<ServiceHealth, 'status' | 'latency_ms'>[] = [
  { name: 'Core API', port: 8000 },
  { name: 'CRM',      port: 8101 },
  { name: 'Incident', port: 8102 },
  { name: 'Workforce',port: 8103 },
  { name: 'Comms',    port: 8104 },
];

const STATUS_DOT: Record<ServiceHealthStatus, string> = {
  online:   'bg-ops-emerald',
  degraded: 'bg-ops-orange',
  offline:  'bg-ops-rose',
  checking: 'bg-ink-muted animate-pulse',
};

export function HealthStrip() {
  const [services, setServices] = useState<ServiceHealth[]>(
    SERVICES.map((s) => ({ ...s, status: 'checking' })),
  );
  const [lastChecked, setLastChecked] = useState<string | null>(null);

  const checkHealth = async () => {
    const start = Date.now();
    try {
      const res = await fetch('/api/v1/system/health', { signal: AbortSignal.timeout(5000) });
      const body = res.ok ? await res.json() : null;

      setServices((prev) =>
        prev.map((svc) => {
          if (svc.name === 'Core API') {
            return { ...svc, status: res.ok ? 'online' : 'offline', latency_ms: Date.now() - start };
          }
          // Try to match tool service health from the nested body
          const key = svc.name.toLowerCase();
          const raw = body?.tools?.[key] ?? body?.[key];
          let status: ServiceHealthStatus = 'checking';
          if (raw?.status === 'healthy' || raw?.status === 'ok') status = 'online';
          else if (raw?.status === 'degraded') status = 'degraded';
          else if (raw) status = 'offline';
          else status = res.ok ? 'online' : 'offline'; // fallback: if core is up, assume tools reachable
          return { ...svc, status };
        }),
      );
    } catch {
      setServices((prev) => prev.map((s) => ({ ...s, status: 'offline' })));
    }
    setLastChecked(new Date().toLocaleTimeString());
  };

  useEffect(() => {
    checkHealth();
    const t = setInterval(checkHealth, 30_000);
    return () => clearInterval(t);
  }, []); // eslint-disable-line react-hooks/exhaustive-deps

  const overallOnline = services.filter((s) => s.status === 'online').length;

  return (
    <div className="bg-ink-primary text-white px-5 sm:px-8 py-2.5 flex items-center gap-5 overflow-x-auto">
      <div className="flex items-center gap-2.5 shrink-0">
        <span className="relative flex w-2 h-2">
          <span className={`absolute inset-0 rounded-full ${overallOnline === services.length ? 'bg-ops-emerald' : 'bg-ops-orange'} animate-ping opacity-40`} />
          <span className={`relative w-2 h-2 rounded-full ${overallOnline === services.length ? 'bg-ops-emerald' : 'bg-ops-orange'}`} />
        </span>
        <span className="text-[9px] font-mono text-white/50 uppercase tracking-[0.16em]">Evidence network</span>
        <span className="text-[9px] font-mono font-semibold text-white">
          {overallOnline}/{services.length} ready
        </span>
      </div>

      <div className="h-4 w-px bg-white/15 shrink-0" />

      <div className="flex items-center gap-4">
        {services.map((svc) => (
          <div key={svc.name} className="flex items-center gap-1.5 shrink-0">
            <div className={`w-1.5 h-1.5 rounded-full ${STATUS_DOT[svc.status]}`} />
            <span className="text-[9px] font-mono text-white/60 uppercase tracking-wider">
              {svc.name}
            </span>
            {svc.latency_ms !== undefined && (
              <span className="text-[9px] text-white/30 font-mono hidden lg:block">
                {svc.latency_ms}ms
              </span>
            )}
          </div>
        ))}
      </div>

      <div className="ml-auto shrink-0 hidden md:flex items-center gap-3">
        {lastChecked && (
          <span className="text-[9px] font-mono text-white/30">checked {lastChecked}</span>
        )}
        <button
          onClick={checkHealth}
          className="text-[9px] font-mono text-white/60 hover:text-white transition-colors uppercase tracking-[0.15em] focus-ring rounded"
        >
          Refresh
        </button>
      </div>
    </div>
  );
}
