import { Link, useLocation } from 'react-router-dom';

export function Shell({ children }: { children: React.ReactNode }) {
  const location = useLocation();
  const isRunPage = location.pathname.startsWith('/run/');

  return (
    <div className="min-h-screen bg-void flex flex-col">
      {/* ── Top navigation bar ──────────────────────────────────── */}
      <header className="sticky top-0 z-50 bg-abyss border-b border-border-dim flex items-center justify-between px-6 h-14 shrink-0">
        <Link to="/" className="flex items-center gap-3 group">
          {/* Logo mark */}
          <div className="relative w-7 h-7 shrink-0">
            <div className="absolute inset-0 rounded bg-ops-amber/10 border border-ops-amber/30 group-hover:bg-ops-amber/20 transition-colors" />
            <svg viewBox="0 0 28 28" fill="none" className="w-7 h-7 relative z-10">
              <circle cx="14" cy="14" r="5" stroke="#f59e0b" strokeWidth="1.5" />
              <path d="M14 3 L14 7 M14 21 L14 25 M3 14 L7 14 M21 14 L25 14"
                stroke="#f59e0b" strokeWidth="1.5" strokeLinecap="round" />
              <circle cx="14" cy="14" r="2" fill="#f59e0b" />
            </svg>
          </div>
          <span className="font-semibold text-ink-primary tracking-tight group-hover:text-ops-amber-bright transition-colors">
            OptiFlow <span className="text-ops-amber">AI</span>
          </span>
        </Link>

        <nav className="flex items-center gap-6">
          {isRunPage && (
            <Link
              to="/"
              className="text-xs font-mono text-ink-secondary hover:text-ink-primary transition-colors tracking-widest uppercase"
            >
              ← Control Room
            </Link>
          )}
          <span className="text-xs font-mono text-ink-muted uppercase tracking-widest hidden sm:block">
            Mission Control
          </span>
          <div className="flex items-center gap-2">
            <div className="relative w-2 h-2 shrink-0">
              <div className="absolute inset-0 rounded-full bg-ops-emerald" />
              <div className="absolute inset-0 rounded-full bg-ops-emerald animate-ping opacity-75" />
            </div>
            <span className="text-xs font-mono text-ops-emerald">LIVE</span>
          </div>
        </nav>
      </header>

      {/* ── Page content ────────────────────────────────────────── */}
      <main className="flex-1 overflow-auto">
        {children}
      </main>
    </div>
  );
}
