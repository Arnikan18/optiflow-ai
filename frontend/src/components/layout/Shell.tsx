import { Link, useLocation } from 'react-router-dom';

export function Shell({ children }: { children: React.ReactNode }) {
  const location = useLocation();
  const isRunPage = location.pathname.startsWith('/run/');

  return (
    <div className="min-h-screen bg-void flex flex-col overflow-x-hidden">
      <header className="sticky top-0 z-50 h-16 shrink-0 border-b border-border-dim bg-abyss/95 backdrop-blur">
        <div className="h-full max-w-[1440px] mx-auto px-5 sm:px-8 flex items-center justify-between">
          <Link to="/" className="group flex items-center gap-3 focus-ring rounded-lg">
            <div className="relative w-9 h-9 rounded-xl bg-ink-primary overflow-hidden shadow-card">
              <svg viewBox="0 0 36 36" fill="none" className="w-full h-full" aria-hidden="true">
                <path d="M8 10h8c5.5 0 5.5 8 11 8h1" stroke="#fffdf8" strokeWidth="2.2" strokeLinecap="round" />
                <path d="M8 26h8c5.5 0 5.5-8 11-8h1" stroke="#f05a2a" strokeWidth="2.2" strokeLinecap="round" />
                <circle cx="8" cy="10" r="2.5" fill="#fffdf8" />
                <circle cx="8" cy="26" r="2.5" fill="#f05a2a" />
                <circle cx="28" cy="18" r="3" fill="#fffdf8" />
              </svg>
            </div>
            <div>
              <div className="text-[15px] leading-none font-extrabold tracking-[-0.03em] text-ink-primary">
                optiflow
              </div>
              <div className="text-[9px] mt-1 font-mono uppercase tracking-[0.22em] text-ink-muted">
                decision systems
              </div>
            </div>
          </Link>

          <nav className="flex items-center gap-3 sm:gap-6">
            {isRunPage && (
              <Link
                to="/"
                className="hidden sm:flex items-center gap-2 text-xs font-semibold text-ink-secondary hover:text-ink-primary transition-colors focus-ring rounded-md"
              >
                <span aria-hidden="true">←</span>
                New decision
              </Link>
            )}
            <div className="hidden md:flex items-center gap-2 text-[10px] font-mono uppercase tracking-[0.16em] text-ink-muted">
              <span className="w-1.5 h-1.5 rounded-full bg-ops-emerald" />
              human governed
            </div>
            <div className="h-5 w-px bg-border-dim hidden md:block" />
            <div className="flex items-center gap-2 px-3 py-1.5 rounded-full border border-border-dim bg-deep">
              <span className="relative flex w-2 h-2">
                <span className="absolute inset-0 rounded-full bg-ops-emerald animate-ping opacity-40" />
                <span className="relative w-2 h-2 rounded-full bg-ops-emerald" />
              </span>
              <span className="text-[10px] font-mono font-semibold uppercase tracking-[0.14em] text-ink-secondary">
                systems live
              </span>
            </div>
          </nav>
        </div>
      </header>

      <main className="flex-1 min-h-0 min-w-0">{children}</main>
    </div>
  );
}
