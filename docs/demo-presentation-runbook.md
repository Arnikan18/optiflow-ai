# OptiFlow Demo Presentation Runbook

## The demo has two moments, not two presentation apps

Use **Today's Goal** for the team presentation. It is the normal manager
experience and tells the controlled story from a real problem to a verified
decision.

Use **Judge Mode** afterward for free exploration. Judges change authoritative
enterprise values and can verify that OptiFlow performs a fresh governed
analysis rather than replaying a recording.

## Fresh-laptop start

Prerequisites are Docker Desktop and Node.js 22 LTS.

From the repository root in PowerShell:

```powershell
Copy-Item .env.example .env
.\scripts\start-demo.ps1 -ResetData -PreferenceProfile SLA_FIRST
```

The launcher:

1. builds and starts PostgreSQL, Core, CRM, Incident, Workforce, and
   Communication in Docker;
2. restores deterministic enterprise demo data;
3. seeds 18 preference decisions, including 14 SLA-First choices;
4. installs frontend dependencies; and
5. starts the frontend locally at `http://localhost:3000`.

The frontend is intentionally not a Docker service. On later starts, use:

```powershell
.\scripts\start-demo.ps1 -SkipBuild -SkipInstall
```

## What each page is for

| Page | One job |
|---|---|
| Today's Goal | See today's people and problems, then start a governed decision for one selected problem |
| Run | Follow the eight-step route and act only when the system needs a human |
| Judge Mode | Change live incident or workforce data and compare before, live, and AI states |
| Decisions | Reopen runs and review recorded outcomes and human reasons |
| Settings | Change appearance or connect an optional AI explanation provider |

Details stay collapsed until requested. The primary action is always visible;
alternatives, raw evidence, preference history, and manual allocation are
progressively disclosed.

## Presentation path

### 1. Establish the operating picture — Today's Goal

Open `http://localhost:3000`.

- Point to the available workers and their compact effectiveness/capacity
  metrics.
- Point to the priority-ordered problem bar.
- Select the highest-priority problem. Its evidence and goal input unfold
  directly beneath that problem.

Say: “The manager starts from a live operational problem, not an empty AI
chat.”

### 2. Start the governed agent

Use:

```text
Protect strategic renewals while minimizing SLA breaches and specialist overload.
```

Start the analysis. The app opens the run automatically.

- Let the eight-step route advance.
- Select **Evidence** once to reveal which enterprise systems and values were
  used.
- Keep the other step details closed.

Say: “Every decision is reproducible: the route shows what was fetched, why it
was used, and where human authority begins.”

### 3. Make the first human decision

At the approval gate:

- Show the single recommended strategy and its key trade-offs.
- Open preference details briefly to show the learned SLA-First history.
- Approve the recommendation and enter a short business reason.

The system executes through the same reservation, communication, assignment,
confirmation, and verification SAGA used by every plan.

Say: “The AI recommends; the manager remains accountable; the system records
the reason.”

### 4. Show the verified outcome

Wait for **Completed** and **Verified**.

- Open only the verification step.
- Visit **Decisions** to show the outcome and recorded human reason.

### 5. Hand control to the judges — Judge Mode

Open **Judge Mode**.

Choose one clear change:

- make a specialist unavailable; or
- raise an incident priority and shorten its SLA.

Apply the change with automatic analysis enabled.

The comparison card shows:

```text
Before → authoritative live value → AI response
```

Open the generated run and compare the new recommendation. If the strategy
does not change, say so: stability is a valid decision when the existing plan
remains optimal.

### 6. Demonstrate human override and learning

At the new approval gate, judges can:

1. approve the recommendation;
2. reject it and choose another generated plan;
3. request a natural-language modification;
4. open the manual-assignment fallback; or
5. reject all plans and stop safely.

Every path requests a reason. Alternative choices, modifications, rejections,
and manual decisions are recorded for later preference learning.

## Recommended judge experiments

Use one experiment at a time so the cause and effect remain obvious.

| Judge change | What to watch |
|---|---|
| Worker unavailable | Feasible assignments and recommendation may change |
| Worker capacity reduced | Over-capacity choices disappear |
| Incident priority raised | Portfolio order and consequence scores change |
| SLA shortened | SLA-oriented plan may become stronger |
| Choose an alternative | Decision history records an override |
| Request changes | The route generates revised plans and returns to approval |
| Manual assignment | Skills, availability, capacity, duplicates, and conflicts are validated before execution |

## Reset and recovery

Restore operational demo data without deleting volumes:

```powershell
.\scripts\reset-demo.ps1
```

Restore the mature SLA preference:

```powershell
docker compose exec -T core-api python -m scripts.seed_preference_demo --profile SLA_FIRST --decisions 18 --preferred-count 14 --apply
```

Check every backend:

```powershell
.\scripts\health-check.ps1
```

Stop the frontend with `Ctrl+C`. Stop backend containers with:

```powershell
docker compose --profile full-stack down
```

Use volume deletion only when all local demo history may be discarded.

## Demo success checklist

- Six backend services are healthy.
- Today's Goal loads workers and priority-ordered problems.
- A run reaches the approval gate.
- Approval executes and reaches verified completion.
- Judge edits persist to the service-owned databases.
- A judge edit starts a fresh run and shows before/live/AI values.
- Human reason and source appear in decision/preference history.
- Refreshing the browser does not erase backend state.

