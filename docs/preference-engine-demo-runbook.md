# Preference Engine Demo Runbook

## What the demo now shows

The Live Demo page contains a second visible engine named **Preference Engine**.
It reads persisted Core data and shows:

- the current learning state: `COLD_START`, `LEARNING`, or `MATURE`;
- the manager's dominant optimization profile;
- selection counts for Balanced, SLA First, Revenue First, and Fairness First;
- recommendation confidence and acceptance rate;
- recently approved, overridden, or rejected decisions;
- remembered goal constraints.

The card polls Core every three seconds. After a plan decision reaches the
`update_preference_memory` graph node, the card updates without a page refresh.

## API

```text
GET /api/v1/preferences/summary?recent_limit=6
```

The endpoint reads the singleton `manager_preferences` record and recent
`PREFERENCE_MEM_UPDATED` run events. The current deployment stores Core data in
PostgreSQL. The contract remains independent of the database engine.

## Seed a mature demo safely

The seed command is dry-run by default:

```powershell
docker compose exec -T core-api python scripts/seed_preference_demo.py
```

After reviewing the plan, apply it:

```powershell
docker compose exec -T core-api python scripts/seed_preference_demo.py --apply
```

The default seed creates 18 decisions, with 14 favoring `SLA_FIRST`. Before
changing the singleton manager memory, it writes the previous value to:

```text
/tmp/optiflow-preference-memory-backup.json
```

Copy that backup out of the Core container if it must survive recreation:

```powershell
docker cp optiflow-core:/tmp/optiflow-preference-memory-backup.json ./preference-memory-backup.json
```

Custom example:

```powershell
docker compose exec -T core-api python scripts/seed_preference_demo.py --profile REVENUE_FIRST --decisions 18 --preferred-count 14 --apply
```

Only audit runs beginning with `RUN-PREF-DEMO-` are replaced. Ordinary run
history is not deleted.

## Runtime configuration

These environment variables are supported:

```text
COLD_START_RUNS=5
MATURE_LEARNING_RUNS=20
PREFERENCE_CONFIDENCE_LOW_THRESHOLD=0.40
PREFERENCE_CONFIDENCE_HIGH_THRESHOLD=0.70
PREFERENCE_PROFILE_WEIGHT=0.70
PREFERENCE_GOAL_SIMILARITY_WEIGHT=0.30
PREFERENCE_DOMINANCE_FACTOR_WEIGHT=0.60
PREFERENCE_ACCEPTANCE_FACTOR_WEIGHT=0.40
```

Each weight pair must total `1.0`. The mature threshold must be greater than
the cold-start threshold.

## Recommended stage sequence

1. Open `http://localhost:3000/live-demo`.
2. Point out the enterprise-change engine and the separate Preference Engine.
3. Show the recent decisions and the learned dominant profile.
4. Trigger or advance an enterprise event.
5. Wait for the inline AI route to reach the human approval gate.
6. Select a non-recommended profile to demonstrate a manager override.
7. Confirm the plan.
8. Watch the recent-decision card update and explain that the new choice will
   influence later recommendations.

The current UI starts a fresh governed analysis after each enterprise event.
True same-run automatic replanning still requires the simulation callback to be
wired into the active Core run.
