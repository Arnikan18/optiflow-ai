# Today's Goal Decision UI Plan

## Outcome

Turn the landing page into a visual morning decision board. A manager should be
able to understand today's pressure, see who can help, choose or write a goal,
and then follow a transparent decision path without reading long paragraphs.

The redesign keeps Core authoritative. The frontend visualises recorded facts
and clearly labelled derived signals; it does not invent operational outcomes.

## Default Screen

The page will reveal information in this order:

1. **Team orbit** — everyone scheduled in the current portfolio, with
   availability, remaining capacity, workload, reservations, and skill signals.
2. **Today's problems** — dynamically ranked incident cards with a visible
   reason for their order.
3. **Human direction** — choose a problem card to prefill the goal, or write a
   different instruction.
4. **Decision preview** — a compact animated path showing what OptiFlow will
   read, compare, pause on, and verify.

Long explanations will be hidden by default and exposed through `Why?`,
`Evidence`, and `View details` controls.

## Visual Model

### Team orbit

- Central “Today” node with workers arranged as compact orbit cards.
- Availability is shown by state colour and icon.
- A circular gauge shows utilisation.
- Remaining capacity is the main number.
- Skills and reservation details appear on selection.
- Motion follows the saved reduced-motion preference.

The first version uses a **readiness** signal, not a historical effectiveness
claim. Readiness is derived from current operational evidence:

- available today;
- has remaining capacity;
- utilisation is below the safety threshold;
- no conflicting reservation;
- skills are visible for human matching.

True effectiveness needs a later backend contract containing historical
assignment outcomes, SLA performance, quality, and recency.

### Problem priority cards

Until Core exposes the proposed priority contract, cards use a clearly labelled
**live pressure order** calculated from current portfolio facts:

- SLA pressure or an expired deadline;
- incident severity;
- no current owner;
- customer renewal risk;
- customer ARR/business value;
- incident age.

Each card shows only the incident, customer, priority number, deadline state,
ownership state, and top two reasons. Expanding the card reveals the complete
evidence and the exact derived score.

The UI must not describe this provisional order as an authoritative optimiser
decision. The target Core contract should return `priority`, `priority_band`,
`signals`, and `reason`; the presentation layer can then consume those fields
without changing the visual component.

### Decision path

The visual path uses animated nodes and connectors:

`Goal → Frame → Guard → Pull evidence → Compare → Human choice → Execute → Verify`

Selecting a node reveals:

- what data is pulled;
- what check is performed;
- why the route selected that branch;
- what would happen if a different branch were chosen;
- what the manager can do manually.

No node should imply completion until the matching backend event exists.
The active node uses a rotating outer ring, enterprise-source packets travel
towards the evidence node, human gates pulse amber, and rejected or failed
branches remain visible. Replanning draws an explicit loop back to planning.

## Responsive Behaviour

- Desktop: team orbit across the top, priority queue and goal composer below.
- Tablet: horizontal worker carousel, two-column problem cards.
- Mobile: stacked worker strip, one problem card at a time, sticky goal action.
- Keyboard selection and visible focus remain required.
- Animation becomes static when reduced motion is enabled.

## Staged Commits

1. **Decision model foundation**
   - Add a presentation adapter for provisional pressure order and worker
     readiness while the Core priority contract is pending.
   - Keep labels, scores, inputs, and reasons deterministic and inspectable.

2. **Human direction composer**
   - Allow a selected problem to prefill the existing goal input.
   - Preserve free-form human input and the existing approval guarantee.

3. **Today's decision board**
   - Replace the text-heavy landing hierarchy with team orbit, priority cards,
     and the compact goal composer.
   - Keep loading, partial-data, error, refresh, and empty states.

4. **Motion and progressive detail**
   - Add orbit, pulse, and connector animation.
   - Add accessible detail panels and reduced-motion fallbacks.

5. **Run decision tree**
   - Convert the linear journey rail into a responsive decision tree.
   - Show current, completed, waiting, alternate, and stopped branches.

6. **Step teaching and alternatives**
   - Convert causal evidence into compact visual nodes.
   - Add `Pulled`, `Checked`, `Decided`, and `Alternatives` detail groups.
   - Add “Why this?” and “What if?” views backed by events and plan data.

7. **Final validation**
   - Run the TypeScript/Vite production build after every commit.
   - Verify desktop/mobile layouts, keyboard access, theme modes, reduced motion,
     partial evidence, and failed-run truthfulness.

## Initial Acceptance Checks

- Problems appear in a deterministic priority order from live portfolio data.
- Selecting a problem prepares a relevant goal without preventing edits.
- All workers are visible, including unavailable and fully utilised workers.
- The UI says why a worker is or is not ready.
- Default cards stay concise; complete evidence remains available on demand.
- Decision animation never advances beyond the latest recorded run state.
- A manager can inspect an alternate choice without executing it.
