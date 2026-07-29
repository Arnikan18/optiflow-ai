# Member 1 Backend Integration Contract

This contract documents the backend APIs Member 1 should consume from the AI Core execution flow. It does not change LangGraph routing; it describes the current service contracts and safe execution policy.

## Shared Rules

- Tool-service calls require `X-Tool-Token: <TOOL_SHARED_TOKEN>`.
- Admin-only tool endpoints require `X-Admin-Key: <ADMIN_API_KEY>` and must stay server-side.
- Propagate `X-Request-ID` on every call.
- Tool-service success responses use:

```json
{
  "success": true,
  "message": "Request completed successfully",
  "timestamp": "2026-07-29T00:00:00Z",
  "data": {}
}
```

- Tool-service error responses use the same wrapper with `success=false`, an `errorCode`, and a non-2xx HTTP status.
- All timestamps are UTC ISO-8601 strings with `Z`.
- Write operations that can be retried should include an `idempotency_key`.

## Execution Flow

1. Create a tentative reservation in Workforce.
2. Create a specialist assignment request in Communication.
3. Poll the assignment request until it becomes `ACCEPTED`, `REJECTED`, `EXPIRED`, `FAILED`, or the Core polling limit is reached.
4. If `ACCEPTED`, confirm the reservation, assign the incident, then call aggregate execution verification.
5. If `REJECTED`, cancel the reservation, record the rejected specialist-incident pair, and return `REPLAN`.
6. If `EXPIRED` or polling timeout occurs, cancel the reservation and return `REPLAN` or retry according to the current policy.
7. If a service fails, distinguish retriable source failures from business verification failures and never mark the run `COMPLETED`.

## Endpoints

### Create Tentative Reservation

`POST /workforce/api/v1/reservations`

Authentication: `X-Tool-Token`

Required headers:

- `X-Tool-Token`
- `X-Request-ID`

Request body:

```json
{
  "reservation_id": "RES-RUN-001-INC-ALPHA-001-SPEC-MAYA",
  "run_id": "RUN-001",
  "specialist_id": "SPEC-MAYA",
  "incident_id": "INC-ALPHA-001",
  "idempotency_key": "RUN-001:reservation:INC-ALPHA-001:SPEC-MAYA",
  "expires_in_seconds": 300
}
```

Response body: `data` is a reservation with `reservation_id`, `run_id`, `specialist_id`, `incident_id`, `status`, `idempotency_key`, `created_at`, `expires_at`, `confirmed_at`, `cancelled_at`, `cancellation_reason`, `updated_at`.

Idempotency: replaying the same idempotency key with the same payload returns the existing reservation; changing the payload for the same key returns conflict.

Possible errors: `401` missing/invalid tool token, `404` missing specialist, `409` capacity/conflict/duplicate idempotency mismatch, `422` validation error.

### Get Reservation

`GET /workforce/api/v1/reservations/{reservation_id}`

Authentication: `X-Tool-Token`

Polling: safe to call repeatedly. Expired tentative reservations are surfaced as `EXPIRED`.

### Confirm Reservation

`PATCH /workforce/api/v1/reservations/{reservation_id}/confirm`

Authentication: `X-Tool-Token`

Body: none.

Idempotency: repeated confirmation of an already confirmed reservation is safe.

Possible errors: `404` missing reservation, `409` cancelled/expired/invalid transition.

### Cancel Reservation

`DELETE /workforce/api/v1/reservations/{reservation_id}`

Authentication: `X-Tool-Token`

Optional body:

```json
{
  "cancellation_reason": "Specialist rejected assignment"
}
```

Idempotency: repeated cancellation of an already cancelled reservation is safe.

### Verify Reservation

`POST /workforce/api/v1/reservations/verify`

Authentication: `X-Tool-Token`

Request body:

```json
{
  "reservation_id": "RES-RUN-001-INC-ALPHA-001-SPEC-MAYA",
  "expected_run_id": "RUN-001",
  "expected_incident_id": "INC-ALPHA-001",
  "expected_specialist_id": "SPEC-MAYA",
  "expected_status": "CONFIRMED"
}
```

Response body: `verified`, `result`, `reservation_id`, `expected_values`, `actual_values`, `failed_checks`, `checked_at`, `current_status`.

### Create Assignment Request

`POST /communication/api/v1/assignment-requests`

Authentication: `X-Tool-Token`

Request body:

```json
{
  "request_id": "AR-RUN-001-INC-ALPHA-001-SPEC-MAYA",
  "run_id": "RUN-001",
  "incident_id": "INC-ALPHA-001",
  "specialist_id": "SPEC-MAYA",
  "reservation_id": "RES-RUN-001-INC-ALPHA-001-SPEC-MAYA",
  "message": "Please accept this OptiFlow assignment.",
  "idempotency_key": "RUN-001:assignment-request:INC-ALPHA-001:SPEC-MAYA",
  "expires_in_seconds": 900
}
```

Response body: `data` is an assignment request with `request_id`, `run_id`, `incident_id`, `specialist_id`, `reservation_id`, `message`, `status`, `idempotency_key`, `created_at`, `expires_at`, `responded_at`, `response_note`, `response_reason`, `updated_at`.

Idempotency: replaying the same idempotency key with the same payload is safe.

### Get / Poll Assignment Request

`GET /communication/api/v1/assignment-requests/{request_id}`

Authentication: `X-Tool-Token`

Polling: safe to call repeatedly. Use `SAGA_POLL_MAX_ATTEMPTS` and `SAGA_POLL_INTERVAL_SECONDS` from Core settings. Do not treat polling timeout as acceptance.

Terminal statuses: `ACCEPTED`, `REJECTED`, `EXPIRED`, `FAILED`, `CANCELLED`.

### Verify Assignment Request

`POST /communication/api/v1/assignment-requests/verify`

Authentication: `X-Tool-Token`

Request body:

```json
{
  "assignment_request_id": "AR-RUN-001-INC-ALPHA-001-SPEC-MAYA",
  "expected_run_id": "RUN-001",
  "expected_incident_id": "INC-ALPHA-001",
  "expected_specialist_id": "SPEC-MAYA",
  "expected_status": "ACCEPTED"
}
```

Response body: `verified`, `result`, `assignment_request_id`, `expected_values`, `actual_values`, `failed_checks`, `checked_at`, `current_status`.

### Assign Incident

`POST /incident/api/v1/incidents/{incident_id}/assign`

Authentication: `X-Tool-Token`

Request body:

```json
{
  "specialist_id": "SPEC-MAYA",
  "run_id": "RUN-001",
  "idempotency_key": "RUN-001:incident-assign:INC-ALPHA-001:SPEC-MAYA"
}
```

Response body: incident fields including `incident_id`, `customer_id`, `status`, `assigned_specialist_id`, `assignment_run_id`, `assignment_idempotency_key`, `assigned_at`.

Idempotency: repeated assignment with the same run and idempotency context is safe; assigning to a different specialist is a conflict.

### Verify Incident Assignment

`POST /incident/api/v1/incidents/assignment/verify`

Authentication: `X-Tool-Token`

Request body:

```json
{
  "incident_id": "INC-ALPHA-001",
  "expected_run_id": "RUN-001",
  "expected_specialist_id": "SPEC-MAYA"
}
```

Response body: `verified`, `result`, `incident_id`, `expected_values`, `actual_values`, `failed_checks`, `checked_at`, `assignment_status`.

### Aggregate Execution Verification

`POST /api/v1/runs/{run_id}/execution/verify`

Authentication: Core route currently has no browser credential requirement, but it calls internal services with `TOOL_SHARED_TOKEN`.

Required headers:

- `X-Request-ID`

Request body:

```json
{
  "reservation_id": "RES-RUN-001-INC-ALPHA-001-SPEC-MAYA",
  "incident_id": "INC-ALPHA-001",
  "specialist_id": "SPEC-MAYA",
  "assignment_request_id": "AR-RUN-001-INC-ALPHA-001-SPEC-MAYA",
  "plan_id": "PLAN-BALANCED",
  "profile_name": "Balanced"
}
```

Response body: `run_id`, `overall_verified`, `workforce_verification`, `incident_verification`, `communication_verification`, `failed_components`, `checked_at`, `recommended_next_state`, `execution_receipt`.

## State Tables

### Communication Assignment Request

| Current | Event | Next | Notes |
|---|---|---|---|
| `PENDING` | specialist accepts | `ACCEPTED` | Safe to confirm reservation after this. |
| `PENDING` | specialist rejects | `REJECTED` | Cancel reservation and replan. |
| `PENDING` | TTL passes | `EXPIRED` | Cancel reservation and replan or retry. |
| `PENDING` | simulated/tool failure | `FAILED` | Do not complete execution. |
| `ACCEPTED` | any response change | reject | Final state. |
| `REJECTED` | any response change | reject | Final state. |
| `EXPIRED` | any response change | reject | Final state. |

### Workforce Reservation

| Current | Event | Next | Notes |
|---|---|---|---|
| none | create | `TENTATIVE` | Holds capacity until confirmation/cancel/expiry. |
| `TENTATIVE` | confirm | `CONFIRMED` | Increments confirmed workload. |
| `TENTATIVE` | cancel | `CANCELLED` | Releases tentative capacity. |
| `TENTATIVE` | TTL passes | `EXPIRED` | No longer blocks capacity. |
| `CONFIRMED` | confirm again | `CONFIRMED` | Idempotent. |
| `CANCELLED` | cancel again | `CANCELLED` | Idempotent. |

### Incident Assignment

| Current | Event | Next | Notes |
|---|---|---|---|
| unassigned active incident | assign specialist | assigned active | Stores specialist, run, idempotency context and timestamp. |
| assigned to same specialist/run | retry same assignment | assigned active | Safe replay. |
| assigned to another specialist | assign different specialist | conflict | Do not overwrite without explicit workflow. |
| closed/resolved | assign | conflict | Do not assign inactive incidents. |

## Execution Verification Decision Table

| Condition | overall_verified | recommended_next_state |
|---|---:|---|
| Workforce, incident and communication all verified | `true` | `COMPLETED` |
| Any verification source unavailable | `false` | `WAITING` |
| Communication is `PENDING` | `false` | `WAITING` |
| Communication is `REJECTED` or `EXPIRED` | `false` | `REPLAN` |
| Accepted communication but reservation missing/cancelled/expired | `false` | `FAILED` |
| Incident specialist/run mismatch | `false` | `FAILED` |
| Missing required record | `false` | `FAILED` |

## Recommended LangGraph Next State

- `COMPLETED`: persist execution receipt and finish the approved action.
- `WAITING`: keep the run open, retry polling or wait for source recovery.
- `REPLAN`: add excluded specialist-incident pair when applicable and regenerate plans.
- `COMPENSATE`: reserved for policy-specific compensation flows; current aggregate logic primarily returns `REPLAN` for rejection/expiry.
- `FAILED`: safe-pause and require operator review.
