import type { ReactNode } from 'react';
import { Link, NavLink, useLocation } from 'react-router-dom';

type NavIcon = 'today' | 'live' | 'history' | 'lab' | 'settings';

type NavigationItem = {
  number: string;
  label: string;
  shortLabel: string;
  description: string;
  to: string;
  icon: NavIcon;
};

const NAVIGATION: NavigationItem[] = [
  {
    number: '01',
    label: "Today's Goal",
    shortLabel: 'Today',
    description: 'Live goal and decision journey',
    to: '/',
    icon: 'today',
  },
  {
    number: '02',
    label: 'Live Demo',
    shortLabel: 'Live Demo',
    description: 'Timeline and judge challenges',
    to: '/live-demo',
    icon: 'live',
  },
  {
    number: '03',
    label: 'History',
    shortLabel: 'History',
    description: 'Continue and review decisions',
    to: '/history',
    icon: 'history',
  },
  {
    number: '04',
    label: 'Scenario Lab',
    shortLabel: 'Scenarios',
    description: 'Test controlled outcomes',
    to: '/demo-lab',
    icon: 'lab',
  },
  {
    number: '05',
    label: 'Settings',
    shortLabel: 'Settings',
    description: 'Appearance and playback',
    to: '/settings',
    icon: 'settings',
  },
];

function Icon({ name }: { name: NavIcon }) {
  const paths: Record<NavIcon, ReactNode> = {
    today: (
      <>
        <path d="M4 19.5V8.8a2 2 0 0 1 1-1.7l6-3.5a2 2 0 0 1 2 0l6 3.5a2 2 0 0 1 1 1.7v10.7" />
        <path d="M8 21v-7h8v7M3 21h18" />
        <path d="m9.5 10.2 1.6 1.6 3.5-3.6" />
      </>
    ),
    live: (
      <>
        <path d="M3 12h4l2.2-5 4.1 10 2.2-5H21" />
        <circle cx="3" cy="12" r="1.2" />
        <circle cx="21" cy="12" r="1.2" />
      </>
    ),
    history: (
      <>
        <path d="M4 12a8 8 0 1 0 2.3-5.7L4 8.5" />
        <path d="M4 4v4.5h4.5M12 8v4l3 2" />
      </>
    ),
    lab: (
      <>
        <path d="M9 3h6M10 3v6l-5 9a2 2 0 0 0 1.8 3h10.4a2 2 0 0 0 1.8-3l-5-9V3" />
        <path d="M7.5 15h9" />
      </>
    ),
    settings: (
      <>
        <circle cx="12" cy="12" r="3" />
        <path d="M19 13.5v-3l-2-.7-.6-1.4.9-1.9-2.1-2.1-1.9.9-1.4-.6-.7-2h-3l-.7 2-1.4.6-1.9-.9-2.1 2.1.9 1.9-.6 1.4-2 .7v3l2 .7.6 1.4-.9 1.9 2.1 2.1 1.9-.9 1.4.6.7 2h3l.7-2 1.4-.6 1.9.9 2.1-2.1-.9-1.9.6-1.4 2-.7Z" />
      </>
    ),
  };

  return (
    <svg
      viewBox="0 0 24 24"
      fill="none"
      stroke="currentColor"
      strokeWidth="1.6"
      strokeLinecap="round"
      strokeLinejoin="round"
      className="w-5 h-5"
      aria-hidden="true"
    >
      {paths[name]}
    </svg>
  );
}

function isItemActive(pathname: string, item: NavigationItem): boolean {
  if (item.to === '/') {
    return pathname === '/' || pathname.startsWith('/run/');
  }
  return pathname.startsWith(item.to);
}

export function Shell({ children }: { children: ReactNode }) {
  const { pathname } = useLocation();
  const isRunPage = pathname.startsWith('/run/');
  const isLiveDemoPage = pathname.startsWith('/live-demo');

  return (
    <div className="min-h-screen bg-void flex flex-col overflow-x-hidden">
      <header className="sticky top-0 z-50 h-16 shrink-0 border-b border-border-dim bg-abyss/95 backdrop-blur">
        <div className="h-full px-4 sm:px-6 flex items-center justify-between gap-4">
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
                decision atlas
              </div>
            </div>
          </Link>

          <div className="flex items-center gap-3">
            {isLiveDemoPage && (
              <span className="hidden sm:inline-flex items-center gap-2 rounded-full border border-ops-violet/30 bg-ops-violet/10 px-3 py-1.5 text-xs font-mono font-bold uppercase tracking-[0.12em] text-ops-violet">
                <span className="w-1.5 h-1.5 rounded-full bg-ops-violet animate-pulse" />
                Live demo mode
              </span>
            )}
            {isRunPage && (
              <Link
                to="/"
                className="hidden sm:flex items-center gap-2 text-xs font-semibold text-ink-secondary hover:text-ops-amber transition-colors focus-ring rounded-md"
              >
                <span aria-hidden="true">＋</span>
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
              <span className="hidden sm:inline text-[10px] font-mono font-semibold uppercase tracking-[0.14em] text-ink-secondary">
                systems live
              </span>
            </div>
          </div>
        </div>
      </header>

      <nav
        className="lg:hidden sticky top-16 z-40 border-b border-border-dim bg-abyss/95 backdrop-blur overflow-x-auto"
        aria-label="Decision workspace"
      >
        <div className="min-w-max px-3 flex">
          {NAVIGATION.map((item) => {
            const active = isItemActive(pathname, item);
            return (
              <NavLink
                key={item.to}
                to={item.to}
                aria-current={active ? 'page' : undefined}
                className={`relative flex items-center gap-2 px-3.5 py-3 text-xs font-semibold transition-colors focus-ring ${
                  active ? 'text-ink-primary' : 'text-ink-muted hover:text-ink-primary'
                }`}
              >
                <Icon name={item.icon} />
                {item.shortLabel}
                {active && <span className="absolute left-3 right-3 bottom-0 h-0.5 bg-ops-amber" />}
              </NavLink>
            );
          })}
        </div>
      </nav>

      <div className="flex flex-1 min-h-0">
        <aside className="hidden lg:flex w-60 shrink-0 sticky top-16 self-start h-[calc(100vh-4rem)] border-r border-border-dim bg-abyss flex-col">
          <div className="px-5 pt-6 pb-4">
            <p className="text-[9px] font-mono uppercase tracking-[0.2em] text-ink-muted">
              Decision workspace
            </p>
            <p className="text-xs leading-relaxed text-ink-secondary mt-2">
              Set today's goal, understand each choice, and return to any outcome.
            </p>
          </div>

          <nav className="px-3 space-y-1" aria-label="Decision workspace">
            {NAVIGATION.map((item) => {
              const active = isItemActive(pathname, item);
              return (
                <NavLink
                  key={item.to}
                  to={item.to}
                  aria-current={active ? 'page' : undefined}
                  className={`group relative grid grid-cols-[32px_1fr] gap-3 rounded-xl px-3 py-3.5 transition-all focus-ring ${
                    active
                      ? 'bg-ink-primary text-white shadow-card'
                      : 'text-ink-secondary hover:bg-deep hover:text-ink-primary'
                  }`}
                >
                  <div className={`w-8 h-8 rounded-lg flex items-center justify-center ${
                    active ? 'bg-white/10 text-[#ff8a64]' : 'bg-deep text-ink-muted group-hover:text-ops-cyan'
                  }`}>
                    <Icon name={item.icon} />
                  </div>
                  <div className="min-w-0">
                    <div className="flex items-center justify-between gap-2">
                      <span className="text-xs font-bold">{item.label}</span>
                      <span className={`text-[8px] font-mono ${active ? 'text-white/40' : 'text-ink-ghost'}`}>
                        {item.number}
                      </span>
                    </div>
                    <p className={`text-[9px] leading-relaxed mt-1 ${
                      active ? 'text-white/55' : 'text-ink-muted'
                    }`}>
                      {item.description}
                    </p>
                  </div>
                  {active && (
                    <span className="absolute -right-px top-3 bottom-3 w-1 rounded-l-full bg-ops-amber" />
                  )}
                </NavLink>
              );
            })}
          </nav>

          <div className="mt-auto p-4">
            <div className="rounded-2xl border border-border-dim bg-deep p-4">
              <div className="flex items-center gap-2">
                <span className="w-2 h-2 rounded-full bg-ops-emerald" />
                <span className="text-[9px] font-mono font-semibold uppercase tracking-[0.14em] text-ink-secondary">
                  Manual route ready
                </span>
              </div>
              <p className="text-[10px] leading-relaxed text-ink-muted mt-2">
                Every automated step will include a human fallback.
              </p>
            </div>
          </div>
        </aside>

        <main className="flex-1 min-h-0 min-w-0">{children}</main>
      </div>
    </div>
  );
}
