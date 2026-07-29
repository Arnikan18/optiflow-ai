type WorkspacePageProps = {
  eyebrow: string;
  title: string;
  description: string;
  purpose: string;
  capabilities: string[];
};

function WorkspacePage({
  eyebrow,
  title,
  description,
  purpose,
  capabilities,
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
                Workspace purpose
              </p>
              <p className="text-xl font-extrabold tracking-[-0.04em] text-ink-primary mt-3">
                {purpose}
              </p>
              <ul className="mt-5 space-y-3">
                {capabilities.map((capability) => (
                  <li key={capability} className="flex gap-3 text-sm leading-relaxed text-ink-secondary">
                    <span className="mt-2 w-1.5 h-1.5 shrink-0 rounded-full bg-ops-cyan" />
                    <span>{capability}</span>
                  </li>
                ))}
              </ul>
              <div className="mt-6 pt-5 border-t border-border-dim flex items-center gap-2 text-[10px] font-mono uppercase tracking-[0.14em] text-ops-emerald">
                <span className="w-2 h-2 rounded-full bg-ops-emerald" />
                Connected to Core
              </div>
            </div>
          </aside>
        </div>
      </section>
    </div>
  );
}

export function RunHistoryPage() {
  return (
    <WorkspacePage
      eyebrow="History"
      title="Your decision record."
      description="Return to active and completed goals without losing the evidence, alternatives, approvals, and outcomes that shaped them."
      purpose="Resume, compare, and learn"
      capabilities={[
        'Continue an active decision from its latest verified step.',
        'Review why a plan won and what alternatives were rejected.',
        'Repeat an earlier goal with the latest portfolio evidence.',
      ]}
    />
  );
}

export function DemoLabPage() {
  return (
    <WorkspacePage
      eyebrow="Scenario lab"
      title="Test the route before it matters."
      description="Explore controlled operational situations with the same checks used by a live decision, without changing real work."
      purpose="Practise safely with real logic"
      capabilities={[
        'Queue specialist responses and observe how the route adapts.',
        'Simulate a source failure and inspect the manual fallback.',
        'Reset the demonstration state for a repeatable walkthrough.',
      ]}
    />
  );
}

export function SettingsPage() {
  return (
    <WorkspacePage
      eyebrow="Settings"
      title="Make OptiFlow work your way."
      description="Control appearance, guided playback, motion, and how much engine detail is revealed while a decision unfolds."
      purpose="Personalize without hiding the truth"
      capabilities={[
        'Choose light, dark, or system appearance.',
        'Adjust readable step timing and reduced-motion behavior.',
        'Choose rules-only or AI-assisted explanations when available.',
      ]}
    />
  );
}
