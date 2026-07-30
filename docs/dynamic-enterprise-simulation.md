# Dynamic Enterprise Simulation Backend

## Overview

NeuroX Phase 2 adds a backend-only dynamic enterprise simulation layer while preserving the existing AI run pipeline.

Flow:

```text
Scenario Loader
Timeline Simulator
Enterprise Event Engine
Enterprise Services / Databases
Enterprise Change Notification
Simulation Coordinator
```

The simulation package lives in `core-api/app/simulation`. It does not import LangGraph, optimizer, evidence planner, candidate comparison, approval, execution, or preference-memory modules.

## Architecture

- `scenario_loader.py` discovers scenario folders dynamically from `SIMULATION_SCENARIO_ROOT`.
- `timeline_simulator.py` owns simulation state transitions, timeline position, current stage, processed events, and reset/start/pause/resume/advance behavior.
- `enterprise_event_engine.py` validates enterprise events, applies service-owned updates through HTTP APIs, records event history, and creates notification outbox entries.
- Tool services continue to own enterprise data in their own SQLite databases.
- Core stores only simulation run state, event history, and notification outbox rows.

## Scenario Format

Scenarios live under:

```text
scenarios/
  product_release_day/
    metadata.json
    initial_state.json
    timeline.json
```

`metadata.json` contains `scenario_id`, `name`, `description`, `version`, `mode`, `duration`, `start_time`, `end_time`, `timezone`, `stages`, `tags`, `schema_version`, and `created_at`.

`initial_state.json` supports `customers`, `specialists`, `incidents`, `assignments`, `reservations`, `notifications`, `workloads`, `sla_data`, and `supporting_data`.

`timeline.json` is an ordered array of events with `event_id`, `scenario_id`, `scheduled_time`, `stage`, `event_type`, `payload`, `description`, `sequence`, and `enabled`.

Loader validation rejects missing required files, malformed JSON, duplicate scenario IDs, duplicate event IDs, unsupported event types, invalid stages, out-of-window events, and invalid ordering.

## Event Types

- `NEW_TICKET`
- `RESOLVE_TICKET`
- `ESCALATE_PRIORITY`
- `CHANGE_SLA`
- `CHANGE_ESTIMATED_EFFORT`
- `ENGINEER_ON_LEAVE`
- `ENGINEER_RETURNED`

The public simulation vocabulary says tickets/engineers. The service implementation preserves existing database terminology: incidents and specialists.

## Statuses

- `IDLE`
- `RUNNING`
- `PAUSED`
- `STOPPED`
- `COMPLETED`
- `ERROR`

## API Routes

All responses use:

```json
{
  "success": true,
  "message": "Request completed successfully",
  "timestamp": "2026-07-22T09:00:00Z",
  "data": {}
}
```

Errors use `success=false`, `errorCode`, `message`, `timestamp`, and optional `details`.

| Method | Path | Authentication | Purpose |
| --- | --- | --- | --- |
| `GET` | `/api/v1/simulation/scenarios` | none | List scenario metadata |
| `POST` | `/api/v1/simulation/start` | `DEMO_MODE=true`, `X-Admin-Key` | Load scenario initial state and start TIMELINE or INTERACTIVE mode |
| `POST` | `/api/v1/simulation/pause` | `DEMO_MODE=true`, `X-Admin-Key` | Pause a running simulation |
| `POST` | `/api/v1/simulation/resume` | `DEMO_MODE=true`, `X-Admin-Key` | Resume a paused simulation |
| `POST` | `/api/v1/simulation/reset` | `DEMO_MODE=true`, `X-Admin-Key` | Restore selected scenario initial state and clear temporary event/notification state |
| `GET` | `/api/v1/simulation/status` | none | Read latest simulation status |
| `POST` | `/api/v1/simulation/event` | `DEMO_MODE=true`, `X-Admin-Key` | Inject a judge enterprise event |
| `POST` | `/api/v1/simulation/advance` | `DEMO_MODE=true`, `X-Admin-Key` | Process exactly one next timeline event |
| `GET` | `/api/v1/simulation/events` | none | List event history |
| `GET` | `/api/v1/simulation/notifications` | none | List enterprise-change notification outbox |
| `POST` | `/api/v1/simulation/notifications/{notification_id}/ack` | `DEMO_MODE=true`, `X-Admin-Key` | Acknowledge a notification |

## Request Samples

Start:

```json
{
  "scenario_id": "product_release_day",
  "mode": "TIMELINE",
  "reset_existing": true,
  "auto_advance": false
}
```

Judge event:

```json
{
  "event_type": "ENGINEER_ON_LEAVE",
  "scenario_id": "product_release_day",
  "event_id": "JUDGE-LEAVE-001",
  "idempotency_key": "judge-leave-001",
  "payload": {
    "specialist_id": "SPEC-NIMAL",
    "reason": "Emergency leave"
  }
}
```

Reset:

```json
{
  "scenario_id": "product_release_day"
}
```

## Member 1 Contract

Member 1 can implement:

```text
Timeline
AI Run
Approval
Execution
Advance Timeline
```

Use `GET /api/v1/simulation/status` before starting a run. After approved execution completes, call `POST /api/v1/simulation/advance` with `X-Admin-Key`. The advance response includes the processed event, next event, current time/stage, and `completed`.

Use `GET /api/v1/simulation/notifications` to poll for enterprise-change notifications. Acknowledge with `POST /api/v1/simulation/notifications/{notification_id}/ack` if the coordinator tracks consumed notifications.

Idempotency:

- Timeline event processing uses the timeline `event_id` as the idempotency key.
- Judge events should send `idempotency_key`.
- Duplicate event IDs or idempotency keys return the existing recorded result and do not duplicate notifications.

Request IDs:

- Send `X-Request-ID`.
- Core forwards it to tool services and echoes it in the response header.

## Member 3 Contract

Frontend-facing operations:

- `GET /api/v1/simulation/scenarios`
- `POST /api/v1/simulation/start`
- `POST /api/v1/simulation/pause`
- `POST /api/v1/simulation/resume`
- `POST /api/v1/simulation/reset`
- `GET /api/v1/simulation/status`
- `POST /api/v1/simulation/event`
- `GET /api/v1/simulation/events`

Do not expose internal credentials in browser code. If the frontend cannot safely hold admin credentials, proxy mutation requests through a protected Core/admin surface.

## Environment Variables

- `SIMULATION_DEFAULT_SCENARIO`
- `SIMULATION_AUTO_ADVANCE`
- `SIMULATION_TIMEZONE`
- `SIMULATION_EVENT_CALLBACK_URL`
- `SIMULATION_EVENT_TIMEOUT_SECONDS`
- `SIMULATION_MAX_EVENT_RETRIES`
- `SIMULATION_SCENARIO_ROOT`

Docker Compose passes these using `${VARIABLE_NAME}` references only.

## Docker And Smoke Test

Validate Compose:

```powershell
docker compose --profile full-stack config --quiet
docker compose --profile full-stack up --build -d
docker compose ps
docker compose logs --tail=100
```

Run the smoke script:

```powershell
powershell -ExecutionPolicy Bypass -File .\scripts\api-smoke-test.ps1
```

## Reset Behavior

Simulation reset reloads the scenario initial state through service-owned admin endpoints:

- CRM customers
- Workforce specialists and reservations
- Incident incidents
- Communication assignment requests and notifications

Core then clears simulation event history and notification outbox rows. It does not delete AI run history.

## Known Limitations

- Notifications use a Core-owned outbox by default. `SIMULATION_EVENT_CALLBACK_URL` enables best-effort HTTP callback delivery.
- Multi-service event application is not a distributed transaction. Partial downstream failure is recorded as `PARTIALLY_APPLIED`.
- Existing tool databases remain SQLite for the MVP; the model fields and repository boundaries are PostgreSQL-compatible.
