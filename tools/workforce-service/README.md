# OptiFlow Workforce Service

The Workforce Service owns specialist capacity, skills, availability, workload, and temporary reservations for OptiFlow AI Phase 2. It helps the core decision process identify specialists who can safely take incident work while enforcing capacity and reservation constraints.

## Architecture

The service is a FastAPI application using SQLAlchemy 2.x async ORM, Pydantic v2, SQLite for the MVP, and pytest. Runtime concerns are split by responsibility:

```text
app/
  api/routes.py
  database/base.py
  database/models.py
  database/seed.py
  database/session.py
  middleware/authentication.py
  middleware/request_context.py
  schemas/requests.py
  schemas/responses.py
  services/failure_service.py
  services/reservation_service.py
  services/specialist_service.py
  config.py
  main.py
```

## Environment

| Variable | Purpose | Default |
| --- | --- | --- |
| `SERVICE_NAME` | Service metadata | `workforce-service` |
| `SERVICE_PORT` | Runtime port | `8103` |
| `ENVIRONMENT` | Runtime environment label | `development` |
| `DATABASE_URL` | SQLAlchemy database URL | `sqlite:///./data/workforce.db` |
| `LOG_LEVEL` | Structured log threshold | `INFO` |
| `TOOL_SHARED_TOKEN` | Required as `X-Tool-Token` on Workforce APIs | `change-me` |
| `ADMIN_API_KEY` | Required as `X-Admin-Key` on `POST /admin/reset` | unset |
| `RESERVATION_TTL_SECONDS` | Default tentative reservation TTL | `300` |
| `MIN_RESERVATION_TTL_SECONDS` | Minimum accepted TTL | `30` |
| `MAX_RESERVATION_TTL_SECONDS` | Maximum accepted TTL | `3600` |
| `ENABLE_SEED_DATA` | Standard seed toggle alias | unset |
| `SEED_ON_STARTUP` | Seed when the specialist table is empty | `true` |
| `REQUEST_ID_HEADER` | Request correlation header | `X-Request-ID` |
| `MAX_REQUEST_ID_LENGTH` | Maximum accepted request ID length | `128` |
| `MAX_PAGE_SIZE` | Standard maximum page size | `100` |
| `INCIDENT_SERVICE_URL` | Future Incident validation hook | unset |

Do not commit real admin keys or `.env` files.

## Installation

```powershell
cd D:\netx\optiflow-ai\tools\workforce-service
python -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install -r requirements.txt
python -m pip install -e ..\..\shared\python
```

## Running

```powershell
$env:DATABASE_URL='sqlite:///./data/workforce.db'
$env:TOOL_SHARED_TOKEN='change-me'
$env:ADMIN_API_KEY='local-admin-key'
python -m uvicorn app.main:app --host 127.0.0.1 --port 8103
```

SQLite is file-based and does not need a separate database server. The service creates the SQLite parent directory automatically only when the configured URL points to a SQLite file. Production should use managed migrations rather than metadata table creation.

## Tests

Tests use isolated temporary SQLite databases and must not touch `data/workforce.db`.

```powershell
python -m compileall app tests
python -m pytest -q
```

If the Windows temp directory is restricted, set `TMP` and `TEMP` to a writable path under `D:\netx`.

## Endpoints

| Method | Path | Auth | Purpose |
| --- | --- | --- | --- |
| `GET` | `/health` | none | Process health |
| `GET` | `/readiness` | none | Database readiness |
| `GET` | `/workforce/api/v1/specialists` | `X-Tool-Token` | List specialists |
| `GET` | `/workforce/api/v1/specialists/available` | `X-Tool-Token` | List operationally available specialists |
| `GET` | `/workforce/api/v1/specialists/{specialist_id}` | `X-Tool-Token` | Retrieve one specialist |
| `GET` | `/workforce/api/v1/workloads` | `X-Tool-Token` | List workload and reservation counts |
| `POST` | `/workforce/api/v1/reservations` | `X-Tool-Token` | Create tentative reservation |
| `GET` | `/workforce/api/v1/reservations/{reservation_id}` | `X-Tool-Token` | Retrieve reservation |
| `PATCH` | `/workforce/api/v1/reservations/{reservation_id}/confirm` | `X-Tool-Token` | Confirm reservation |
| `DELETE` | `/workforce/api/v1/reservations/{reservation_id}` | `X-Tool-Token` | Cancel or release reservation |
| `POST` | `/admin/reset` | `X-Admin-Key` | Reset deterministic demo data |

Deprecated compatibility endpoints remain for current demo/core integration: `/specialists`, `/specialists/{specialist_id}`, `/availability`, `/workload`, `/reservations/tentative`, `/reservations/{reservation_id}/confirm`, `DELETE /reservations/{reservation_id}`, and selected legacy admin/failure-mode endpoints.

## Request Examples

Create reservation:

```json
{
  "reservation_id": "RES-001",
  "run_id": "RUN-001",
  "specialist_id": "SPEC-MAYA",
  "incident_id": "INC-ALPHA-001",
  "idempotency_key": "reserve-RUN-001-INC-ALPHA-001-SPEC-MAYA",
  "expires_in_seconds": 300
}
```

Success envelope:

```json
{
  "success": true,
  "message": "Request completed successfully",
  "timestamp": "2026-07-24T10:00:00Z",
  "data": {}
}
```

Workload records expose `specialist_id`, `assigned_count`, `tentative_reservation_count`, `confirmed_reservation_count`, `available_capacity`, `utilisation_percentage`, and `updated_at`. Core demo portfolio aggregation uses this endpoint instead of reading Workforce SQLite data.

Error envelope:

```json
{
  "success": false,
  "message": "Specialist not found",
  "errorCode": "WORKFORCE_404",
  "timestamp": "2026-07-24T10:00:00Z"
}
```

## Specialist Fields

Specialists expose `specialist_id`, `name`, optional `email`, `skills`, `capacity`, `current_workload`, `availability`, `active`, `effective_workload`, `available_capacity`, `operationally_available`, `created_at`, and `updated_at`. Internal numeric IDs are not exposed.

Skills are stored as normalized child rows in `specialist_skills`. Input is trimmed, lowercased, deduplicated, and empty skill values are rejected. This supports exact skill filtering and future PostgreSQL migration better than comma-separated strings.

## Capacity

`capacity` is the maximum simultaneous confirmed workload. `current_workload` counts confirmed assignments.

Effective workload:

```text
effective_workload = current_workload + active_unexpired_tentative_reservations
```

Available capacity:

```text
available_capacity = capacity - effective_workload
```

A specialist is operationally available only when `active` is true, `availability` is true, and `available_capacity > 0`.

## Reservations

Statuses:

- `TENTATIVE`
- `CONFIRMED`
- `CANCELLED`
- `EXPIRED`

`TENTATIVE` reservations consume one unit of effective capacity until they expire or are cancelled. `CONFIRMED` reservations increment `current_workload` exactly once. `CANCELLED` and `EXPIRED` reservations do not consume capacity. `DELETE` cancels tentative reservations and releases confirmed reservations without physically deleting history.

Duplicate active reservations for the same `specialist_id` and `incident_id` return `WORKFORCE_409`. A new reservation is allowed after the earlier one is `CANCELLED` or `EXPIRED`. `idempotency_key` prevents duplicate reservation creation; a replay with the same key and same payload returns the existing reservation with HTTP 200, while reusing the key for a different payload returns `WORKFORCE_409`. Duplicate `reservation_id` without a matching idempotency replay returns `WORKFORCE_409`.

Expiration is lazy: expired tentative reservations are excluded from capacity calculations and normalized to `EXPIRED` during reservation operations. No background scheduler is used in the MVP.

## Listing And Filters

Specialist list supports `page`, `page_size`, `active`, `availability`, `skill`, `min_available_capacity`, and `search`. Available specialists support `skill`, `required_capacity`, `page`, and `page_size`. Results use database-side filtering and stable `specialist_id` ordering. Page size is capped at 100.

## Incident References

`incident_id` is a logical reference to the Incident Service. Workforce does not import Incident models, open the Incident database, or create cross-service foreign keys. Core AI or a future integration client should verify incident existence if the approved architecture later requires it.

## Seed Data

Startup seeds only when the specialist table is empty. Reset inserts:

| Specialist | Email | Skills | Capacity | Workload | Availability | Active |
| --- | --- | --- | --- | --- | --- | --- |
| `SPEC-MAYA` | `maya.sen@example.test` | billing, technical, integration | 2 | 0 | true | true |
| `SPEC-DANIEL` | `daniel.ruiz@example.test` | technical, enterprise-support | 2 | 1 | true | true |
| `SPEC-NIMAL` | `nimal.perera@example.test` | security, integration | 1 | 1 | true | true |
| `SPEC-PRIYA` | `priya.raman@example.test` | account-management, billing | 3 | 0 | false | true |
| `SPEC-KAI` | `kai.morgan@example.test` | technical, security | 2 | 0 | true | false |

Seed reservations:

| Reservation | Specialist | Incident | Status |
| --- | --- | --- | --- |
| `RES-MAYA-TENTATIVE` | `SPEC-MAYA` | `INC-ALPHA-001` | `TENTATIVE` |
| `RES-DANIEL-CONFIRMED` | `SPEC-DANIEL` | `INC-NOVA-001` | `CONFIRMED` |
| `RES-NIMAL-CONFIRMED` | `SPEC-NIMAL` | `INC-MEDI-001` | `CONFIRMED` |
| `RES-PRIYA-CANCELLED` | `SPEC-PRIYA` | `INC-CANCELLED-001` | `CANCELLED` |
| `RES-DANIEL-EXPIRED` | `SPEC-DANIEL` | `INC-EXPIRED-001` | expired `TENTATIVE`, lazily normalized |

## Error Codes

| Code | Meaning |
| --- | --- |
| `WORKFORCE_401` | Invalid or missing credentials |
| `WORKFORCE_404` | Missing specialist or reservation |
| `WORKFORCE_409` | Duplicate ID, active duplicate reservation, capacity conflict, or invalid reservation state |
| `WORKFORCE_422` | Validation failure |
| `WORKFORCE_500` | Unexpected internal error |
| `WORKFORCE_503` | Database or reset configuration failure |

## Security And Limits

The service validates all external input, rejects unknown request fields on new write APIs, limits page sizes, returns `X-Request-ID` for correlation, hides database errors, avoids raw SQL interpolation, does not expose secrets, protects reset with `X-Admin-Key`, and avoids returning internal numeric IDs.

## SQLite And PostgreSQL

SQLite provides a good MVP file database, but it is not a production-grade multi-instance concurrency solution. The service recalculates capacity inside each transaction and relies on unique constraints and controlled transaction handling, but future PostgreSQL production should use `SELECT FOR UPDATE`, serializable isolation, atomic capacity updates, or optimistic versioning.

Future scheduling work should add shifts, time windows, time zones, planned absences, and audit/history tables for capacity and reservation state changes.
