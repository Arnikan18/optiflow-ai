interface LiveDemoJourneyStripProps {
  hasPortfolio: boolean;
  demoStarted: boolean;
  changeDetected: boolean;
  analysisStarted: boolean;
}

type StepState = 'DONE' | 'NOW' | 'WAIT';

interface JourneyStep {
  label: string;
  detail: string;
  state: StepState;
}

export function LiveDemoJourneyStrip({
  hasPortfolio,
  demoStarted,
  changeDetected,
  analysisStarted,
}: LiveDemoJourneyStripProps) {
  const steps: JourneyStep[] = [
    {
      label: 'Live data',
      detail: 'Current baseline',
      state: hasPortfolio ? 'DONE' : 'NOW',
    },
    {
      label: 'Change',
      detail: 'Judge edits one signal',
      state: changeDetected ? 'DONE' : demoStarted && hasPortfolio ? 'NOW' : 'WAIT',
    },
    {
      label: 'AI compares',
      detail: 'Fresh governed run',
      state: analysisStarted ? 'DONE' : changeDetected ? 'NOW' : 'WAIT',
    },
    {
      label: 'You decide',
      detail: 'Approve or override',
      state: analysisStarted ? 'NOW' : 'WAIT',
    },
    {
      label: 'System learns',
      detail: 'Decision remembered',
      state: 'WAIT',
    },
  ];

  return (
    <section
      className="rounded-[1.5rem] border border-border-dim bg-abyss shadow-card p-4 sm:p-5"
      aria-label="Live demo journey"
    >
      <div className="grid grid-cols-2 sm:grid-cols-5 gap-2">
        {steps.map((step, index) => (
          <div
            key={step.label}
            className={`rounded-xl border px-3 py-3 transition-colors ${
              step.state === 'DONE'
                ? 'border-ops-emerald/30 bg-ops-emerald/[0.06]'
                : step.state === 'NOW'
                  ? 'border-ops-amber/40 bg-ops-amber/[0.08]'
                  : 'border-border-dim bg-deep'
            }`}
          >
            <div className="flex items-center gap-2">
              <span className={`flex h-6 w-6 shrink-0 items-center justify-center rounded-full text-xs font-mono font-bold ${
                step.state === 'DONE'
                  ? 'bg-ops-emerald text-white'
                  : step.state === 'NOW'
                    ? 'bg-ops-amber text-white'
                    : 'border border-border-base text-ink-muted'
              }`}>
                {step.state === 'DONE' ? '✓' : index + 1}
              </span>
              <p className={`text-sm font-extrabold ${
                step.state === 'NOW'
                  ? 'text-ops-amber'
                  : step.state === 'DONE'
                    ? 'text-ops-emerald'
                    : 'text-ink-muted'
              }`}>
                {step.label}
              </p>
            </div>
            <p className="text-xs text-ink-muted mt-2">{step.detail}</p>
          </div>
        ))}
      </div>
    </section>
  );
}
