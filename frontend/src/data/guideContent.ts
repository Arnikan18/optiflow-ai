import type { RunStatus } from '../types/api';

export interface PhaseGuide {
  id: string;
  label: string;
  icon: string;
  matchStatus: RunStatus[];
  matchNodes: string[];
  whatIsHappening: string;
  whyItMatters: string;
  whatToWatch: string;
  actionPrompt: string | null;
  keyConcept: { term: string; definition: string };
}

export const PHASE_GUIDES: PhaseGuide[] = [
  {
    id: 'receive',
    label: 'Goal Received',
    icon: '📥',
    matchStatus: ['RECEIVED'],
    matchNodes: ['receive_goal'],
    whatIsHappening:
      'Your goal text has been registered and a unique Run ID assigned. The agent is initialising its execution context and preparing to parse your intent.',
    whyItMatters:
      'Every action taken from this point forward is permanently linked to this Run ID — creating an immutable, auditable chain of evidence from goal to outcome.',
    whatToWatch:
      'Note the Run ID at the top of the screen. This is your reference number for the entire decision session and can be used to retrieve logs later.',
    actionPrompt: null,
    keyConcept: {
      term: 'Run ID',
      definition:
        'A unique identifier that ties your goal to every piece of evidence gathered, every plan considered, and every action executed. You can trace any decision back to this ID.',
    },
  },
  {
    id: 'interpret',
    label: 'Interpreting Goal',
    icon: '🧠',
    matchStatus: ['RUNNING'],
    matchNodes: ['interpret_goal'],
    whatIsHappening:
      'Google Gemini is reading your natural-language goal and converting it into a structured format: primary objectives, hard constraints, soft preferences, and business horizon. If Gemini is unavailable, a deterministic fallback parser activates automatically.',
    whyItMatters:
      'The quality of interpretation determines which evidence gets collected and how plans are scored. Vague goals produce more conservative, hedged plans.',
    whatToWatch:
      'Watch for the structured goal summary in the timeline. It should reflect your intent accurately — objectives, constraints, and horizon should all be captured.',
    actionPrompt: null,
    keyConcept: {
      term: 'Structured Goal',
      definition:
        'A machine-readable breakdown of your input: primary objective (e.g. "protect SLA"), hard constraints (e.g. "no overtime"), preferences (e.g. "balance workload"), and planning horizon (e.g. "next 48 hours").',
    },
  },
  {
    id: 'validate',
    label: 'Validating Against Policies',
    icon: '🛡️',
    matchStatus: ['RUNNING'],
    matchNodes: ['validate_goal'],
    whatIsHappening:
      'The system is checking your goal against the organisation\'s operational policies, business rules, and known constraint templates. It looks for ambiguities, policy conflicts, and missing critical parameters.',
    whyItMatters:
      'Starting an optimisation run with an ambiguous or policy-conflicting goal wastes compute time and generates plans that may be unusable or unsafe to execute.',
    whatToWatch:
      'If validation finds an issue, the run will pause and ask you a clarification question. This is not an error — it is the system protecting you from a bad allocation.',
    actionPrompt: null,
    keyConcept: {
      term: 'Policy Guard',
      definition:
        'A rule set that checks goals against what the organisation has defined as permissible, mandatory, and requiring explicit human confirmation before proceeding.',
    },
  },
  {
    id: 'clarify',
    label: 'Clarification Needed',
    icon: '❓',
    matchStatus: ['WAITING_FOR_CLARIFICATION'],
    matchNodes: ['pause_for_clarification'],
    whatIsHappening:
      'The goal validator found an ambiguity or a conflict it cannot resolve automatically. The system has safely paused — no evidence has been collected yet — and is waiting for your answer.',
    whyItMatters:
      'Proceeding without clarity here would generate plans built on incorrect assumptions. The AI will never guess when it comes to critical business rules.',
    whatToWatch:
      'Read the clarification question carefully. It is usually asking about tier priority rules, capacity override permissions, or constraint-conflict resolution.',
    actionPrompt:
      'Answer in plain English. Be specific. Example: "Prioritise Tier 1 customers over Tier 2 when capacity is full." Your answer becomes part of the permanent audit trail.',
    keyConcept: {
      term: 'Safe Pause',
      definition:
        'A deliberate halt point where the agent stops execution and waits for manager input. This prevents incorrect assumptions from propagating through the decision chain.',
    },
  },
  {
    id: 'evidence',
    label: 'Gathering Evidence',
    icon: '📡',
    matchStatus: ['RUNNING'],
    matchNodes: ['plan_evidence', 'select_tools', 'execute_tools', 'build_state'],
    whatIsHappening:
      'The system is querying all four enterprise tools (CRM, Incident, Workforce, Communication) to build a complete portfolio snapshot. It tracks the freshness of every data point and flags conflicts where services disagree.',
    whyItMatters:
      'Plans can only be as good as the data behind them. Stale specialist availability or an outdated CRM tier can cause an allocation that looks optimal on paper to fail during execution.',
    whatToWatch:
      'Data freshness indicators. If any source is marked STALE or CONFLICT, the resulting plans will carry a lower confidence score and should be reviewed with extra scrutiny.',
    actionPrompt: null,
    keyConcept: {
      term: 'Evidence Freshness',
      definition:
        "Each data point is timestamped. A specialist's availability updated 5 minutes ago is weighted more heavily than one updated 2 hours ago. Freshness directly affects optimisation confidence.",
    },
  },
  {
    id: 'optimize',
    label: 'Optimising Allocation Plans',
    icon: '⚙️',
    matchStatus: ['RUNNING'],
    matchNodes: ['evaluate_quality', 'generate_plans'],
    whatIsHappening:
      'The CP-SAT solver (Google OR-Tools) is running 4 optimisation profiles simultaneously: Balanced, SLA-First, Revenue-First, and Fairness-First. Each profile applies a different scoring weight to the same underlying constraint model.',
    whyItMatters:
      'There is no single "best" allocation — it depends on what your organisation values most today. The solver makes those trade-offs explicit and quantified rather than hidden inside a black box.',
    whatToWatch:
      'Solver status (OPTIMAL vs FEASIBLE) and solving time. OPTIMAL means the mathematically best answer was found. FEASIBLE means a high-quality answer was found within the time limit.',
    actionPrompt: null,
    keyConcept: {
      term: 'CP-SAT',
      definition:
        'Constraint Programming – Satisfiability. Searches for the best possible assignment under hard constraints (must not be violated) and soft constraints (should be minimised but can flex). Used by Google Operations Research team.',
    },
  },
  {
    id: 'approval',
    label: 'Your Decision Required',
    icon: '⚡',
    matchStatus: ['WAITING_FOR_APPROVAL'],
    matchNodes: ['pause_for_approval'],
    whatIsHappening:
      'The AI has completed its analysis and generated 4 candidate allocation plans. It has paused execution and is waiting for your review and explicit approval before writing any changes to enterprise systems.',
    whyItMatters:
      'This is the most consequential moment. Nothing has changed in any system yet. You are evaluating proposals, not confirming something that already happened. Your approval triggers real SAGA transactions.',
    whatToWatch:
      'Compare metrics across plans: ARR protected, SLA coverage rate, unassigned incidents. Read the Markdown explanation for the system-recommended plan. Check whether the recommendation matches your current business priority.',
    actionPrompt:
      'Compare all 4 plans. Read the full explanation for the gold-highlighted (recommended) plan. Ask: does this allocation serve my team\'s priority today? Then approve or request a modification.',
    keyConcept: {
      term: 'Human-in-the-Loop',
      definition:
        'A deliberate architectural decision: the AI never executes high-impact allocation changes without explicit manager authorisation. Your approval is the required gate between analysis and action.',
    },
  },
  {
    id: 'executing',
    label: 'Executing Approved Plan',
    icon: '🔄',
    matchStatus: ['EXECUTING'],
    matchNodes: ['execute_saga'],
    whatIsHappening:
      'The system is executing your approved allocation using a SAGA transaction pattern. Each step (workforce reservation, incident assignment, notification dispatch) is individually verified before the next step begins.',
    whyItMatters:
      'SAGA ensures that if any step fails, all previous steps are automatically rolled back. You will never be left with specialists partially assigned or incidents in an inconsistent state.',
    whatToWatch:
      'The execution log — each reservation and assignment confirmation appears as it commits. If any step fails, the system stops immediately and reports the exact failure point.',
    actionPrompt: null,
    keyConcept: {
      term: 'SAGA Transaction',
      definition:
        'A sequence of operations where each step is confirmed before the next begins. A failure at step N triggers automatic compensating rollbacks of steps 1 through N-1, preserving data consistency.',
    },
  },
  {
    id: 'complete',
    label: 'Mission Complete',
    icon: '✅',
    matchStatus: ['COMPLETED'],
    matchNodes: ['complete_run'],
    whatIsHappening:
      'All allocation changes have been successfully committed to enterprise systems. Specialists have been assigned, incidents updated, and communications dispatched. The full audit trail is now closed.',
    whyItMatters:
      'The complete record — goal, evidence, plans, your decision, execution receipts — is permanently stored and supports any future compliance review, post-mortem, or operational audit.',
    whatToWatch:
      'Execution receipts and final allocation metrics. These confirm precisely what changed in each system as a direct result of your decision.',
    actionPrompt:
      "Review the completion summary. Note which customers are now served and which specialists are assigned. This session's record is your operational log.",
    keyConcept: {
      term: 'Execution Receipts',
      definition:
        'Verifiable records confirming each write operation succeeded: which service was updated, which entity was modified, and the exact timestamp of the change.',
    },
  },
  {
    id: 'failed',
    label: 'Execution Failed',
    icon: '❌',
    matchStatus: ['FAILED'],
    matchNodes: [],
    whatIsHappening:
      'A critical error occurred during execution. The system has halted and automatically rolled back any partial changes. No enterprise data has been left in an inconsistent state.',
    whyItMatters:
      'Safe failure is a design guarantee. The SAGA rollback means no partial allocations were committed. The failure context is fully logged for diagnosis.',
    whatToWatch:
      'The error details panel. Common causes: tool service temporarily unavailable, constraint violation discovered during execution, or a concurrent update conflict.',
    actionPrompt:
      'Review the error message. If caused by a service outage, wait a few minutes and retry. If caused by a constraint conflict, return to the Control Room and submit a revised goal.',
    keyConcept: {
      term: 'Safe Failure',
      definition:
        'When execution fails, the system rolls back all changes and records full context. You can always retry from the beginning without risk of data corruption.',
    },
  },
];

// ─── Agent node display labels ─────────────────────────────────────────────
export const NODE_LABELS: Record<string, string> = {
  receive_goal:          'Goal Registered',
  interpret_goal:        'Interpreting Intent',
  validate_goal:         'Validating Policies',
  pause_for_clarification: 'Paused — Awaiting Clarification',
  plan_evidence:         'Planning Evidence Needs',
  select_tools:          'Selecting Enterprise Tools',
  execute_tools:         'Querying Live Data',
  build_state:           'Building Portfolio Snapshot',
  evaluate_quality:      'Checking Evidence Quality',
  generate_plans:        'Running CP-SAT Optimisation',
  pause_for_approval:    'Paused — Awaiting Manager Approval',
  execute_saga:          'Executing SAGA Transactions',
  complete_run:          'Run Completed',
};

// ─── Guide lookup by status / node ────────────────────────────────────────
export function getActiveGuide(
  status: string | null,
  currentNode: string | null,
): PhaseGuide {
  const guide = PHASE_GUIDES.find(
    (g) =>
      (status && g.matchStatus.includes(status as RunStatus)) ||
      (currentNode && g.matchNodes.includes(currentNode)),
  );
  return guide ?? PHASE_GUIDES[0];
}

// ─── All phases in order, for the phase timeline ──────────────────────────
export const PHASE_TIMELINE: { id: string; label: string; icon: string }[] = [
  { id: 'receive',   label: 'Goal Received',         icon: '📥' },
  { id: 'interpret', label: 'Interpreting Goal',      icon: '🧠' },
  { id: 'validate',  label: 'Validating Policies',    icon: '🛡️' },
  { id: 'evidence',  label: 'Gathering Evidence',     icon: '📡' },
  { id: 'optimize',  label: 'Optimising Plans',       icon: '⚙️' },
  { id: 'approval',  label: 'Your Decision',          icon: '⚡' },
  { id: 'executing', label: 'Executing Changes',      icon: '🔄' },
  { id: 'complete',  label: 'Mission Complete',       icon: '✅' },
];
