import { useEffect, useState } from 'react';
import type { ServiceHealth, ServiceHealthStatus } from '../../types/api';

const SERVICES: Omit<ServiceHealth, 'status' | 'latency_ms'>[] = [
  { name: 'Core API', port: 8000 },
  { name: 'CRM',      port: 8101 },
  { name: 'Incident', port: 8102 },
  { name: 'Workforce',port: 8103 },
  { name: 'Comms',    port: 8104 },
];

const STATUS_COLORS: Record<ServiceHealthStatus, string> = {
  online:   'bg-ops-emerald text-ops-emerald',
  degraded: 'bg-ops-orange text-ops-orange',
  offline:  'bg-ops-rose text-ops-rose',
  checking: 'bg-ink-muted text-ink-muted',
};

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
    <div className="bg-abyss border-b border-border-dim px-6 py-2 flex items-center gap-6 overflow-x-auto">
      <div className="flex items-center gap-2 shrink-0">
        <span className="text-xs font-mono text-ink-muted uppercase tracking-widest">System</span>
        <span className={`text-xs font-mono font-semibold ${overallOnline === services.length ? 'text-ops-emerald' : 'text-ops-orange'}`}>
          {overallOnline}/{services.length} ONLINE
        </span>
      </div>

      <div className="h-4 w-px bg-border-dim shrink-0" />

      <div className="flex items-center gap-4">
        {services.map((svc) => (
          <div key={svc.name} className="flex items-center gap-1.5 shrink-0">
            <div className={`w-1.5 h-1.5 rounded-full ${STATUS_DOT[svc.status]}`} />
            <span className={`text-xs font-mono ${STATUS_COLORS[svc.status].split(' ')[1]}`}>
              {svc.name}
            </span>
            {svc.latency_ms !== undefined && (
              <span className="text-xs text-ink-muted font-mono hidden lg:block">
                {svc.latency_ms}ms
              </span>
            )}
          </div>
        ))}
      </div>

      <div className="ml-auto shrink-0 hidden md:flex items-center gap-2">
        {lastChecked && (
          <span className="text-xs font-mono text-ink-muted">Checked {lastChecked}</span>
        )}
        <button
          onClick={checkHealth}
          className="text-xs font-mono text-ink-secondary hover:text-ops-amber transition-colors uppercase tracking-widest"
        >
          Refresh
        </button>
      </div>
    </div>
  );
}
