import { Link } from 'react-router-dom';
import type { RecentRun } from '../types/api';

type WorkspacePageProps = {
  eyebrow: string;
  title: string;
  description: string;
  station: string;
  nextStep: string;
};

function readRecentRuns(): RecentRun[] {
  try {
    return JSON.parse(localStorage.getItem('optiflow_runs') ?? '[]') as RecentRun[];
  } catch {
    return [];
  }
}

function WorkspacePage({
  eyebrow,
  title,
  description,
  station,
  nextStep,
}: WorkspacePageProps) {
  return (
    <div className="min-h-full paper-noise">
      <section className="max-w-6xl mx-auto px-5 sm:px-8 py-12 lg:py-20">
        <div className="grid lg:grid-cols-[minmax(0,1fr)_320px] gap-8 lg:gap-16 items-start">
          <div>
            <p className="text-[10px] font-mono font-semibold uppercase tracking-[0.2em] text-ops-cyan">
              {eyebrow}
            </p>
            <h1 className="max-w-3xl text-4xl sm:text-6xl font-extrabold tracking-[-0.06em] leading-[1.02] mt-4">
              {title}
            </h1>
            <p className="max-w-2xl text-base sm:text-lg leading-relaxed text-ink-secondary mt-6">
              {description}
            </p>
          </div>

          <aside className="rounded-[1.75rem] border border-border-base bg-abyss shadow-card overflow-hidden">
            <div className="h-1.5 bg-ops-cyan" />
            <div className="p-6">
              <p className="text-[9px] font-mono uppercase tracking-[0.18em] text-ink-muted">
                Build station
              </p>
              <p className="text-5xl font-extrabold tracking-[-0.07em] text-ink-primary mt-3">
                {station}
              </p>
              <p className="text-sm leading-relaxed text-ink-secondary mt-4">
                {nextStep}
              </p>
              <div className="mt-6 pt-5 border-t border-border-dim flex items-center gap-2 text-[10px] font-mono uppercase tracking-[0.14em] text-ops-emerald">
                <span className="w-2 h-2 rounded-full bg-ops-emerald" />
                Route connected
              </div>
            </div>
          </aside>
        </div>
      </section>
    </div>
  );
}

export function DecisionFlowHubPage() {
  const recentRun = readRecentRuns()[0];

  if (recentRun) {
    return (
      <div className="min-h-full paper-noise">
        <section className="max-w-5xl mx-auto px-5 sm:px-8 py-12 lg:py-20">
          <p className="text-[10px] font-mono font-semibold uppercase tracking-[0.2em] text-ops-amber">
            Decision flow
          </p>
          <h1 className="text-4xl sm:text-6xl font-extrabold tracking-[-0.06em] leading-[1.02] mt-4">
            Continue the route.
          </h1>
          <p className="max-w-2xl text-base text-ink-secondary leading-relaxed mt-5">
            Your most recent decision remains available as a permanent, revisitable journey.
          </p>
          <Link
            to={`/run/${recentRun.run_id}`}
            className="group block rounded-[1.75rem] border border-border-base bg-abyss shadow-card p-6 sm:p-8 mt-10 focus-ring"
          >
            <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-6">
              <div>
                <p className="text-[10px] font-mono text-ink-muted">
                  #{recentRun.run_id.slice(0, 12)}
                </p>
                <p className="text-lg sm:text-xl font-bold tracking-[-0.03em] mt-3">
                  {recentRun.goal_text}
                </p>
                <p className="text-xs text-ink-muted mt-3">
                  {recentRun.status.replace(/_/g, ' ')}
                </p>
              </div>
              <span className="shrink-0 w-12 h-12 rounded-full bg-ops-amber text-white flex items-center justify-center group-hover:translate-x-1 transition-transform">
                →
              </span>
            </div>
          </Link>
        </section>
      </div>
    );
  }

  return (
    <WorkspacePage
      eyebrow="Decision flow"
      title="Every decision becomes a route."
      description="Start from Overview to create a decision. Its evidence, checks, alternatives, approval, execution, and verification will remain accessible here."
      station="03"
      nextStep="The guided playback controller and permanent step cards are the next route stations."
    />
  );
}

export function RunHistoryPage() {
  return (
    <WorkspacePage
      eyebrow="Run history"
      title="Return to any decision."
      description="This area will organize completed, active, paused, and recovered runs without hiding the reasoning that produced each outcome."
      station="14"
      nextStep="History filters and outcome comparisons will be connected after the full decision journey is in place."
    />
  );
}

export function DemoLabPage() {
  return (
    <WorkspacePage
      eyebrow="Demo lab"
      title="Test the route before it matters."
      description="Queue specialist responses, simulate a source failure, and reset deterministic data from one controlled workspace."
      station="12"
      nextStep="The lab will use the real demo APIs already validated against the backend."
    />
  );
}

export function SettingsPage() {
  return (
    <WorkspacePage
      eyebrow="Settings"
      title="Choose how the story unfolds."
      description="Guided, presentation, and instant playback modes will live here, alongside motion, timing, and accessibility controls."
      station="15"
      nextStep="Preferences will be added after the playback engine defines the supported timing model."
    />
  );
}
