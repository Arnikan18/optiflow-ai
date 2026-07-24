# OptiFlow Incident Service

The Incident Service owns customer escalation and operational incident records for OptiFlow AI Phase 2. It exposes incident identity, priority, SLA deadlines, lifecycle status, and specialist assignment through REST APIs. Other services should call this service through HTTP and must not read the Incident database directly.

## Architecture

The service is a FastAPI application using SQLAlchemy 2.x async ORM, Pydantic v2, SQLite for the MVP, and pytest. It keeps HTTP routes, validation schemas, business logic, database models, and database session setup separate:

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
  services/incident_service.py
  config.py
  main.py
```

## Environment

| Variable | Purpose | Default |
| --- | --- | --- |
| `SERVICE_NAME` | Service metadata | `incident-service` |
| `SERVICE_PORT` | Runtime port | `8102` |
| `DATABASE_URL` | SQLAlchemy database URL | `sqlite:///./data/incident.db` |
| `TOOL_SHARED_TOKEN` | Required on Incident APIs as `X-Tool-Token` | `change-me` |
| `ADMIN_API_KEY` | Required on `POST /admin/reset` as `X-Admin-Key` | unset |
| `SCENARIO_ID` | Demo scenario metadata | `phase2-demo` |
| `SEED_ON_STARTUP` | Seed when the incident table is empty | `true` |
| `CRM_SERVICE_URL` | Future CRM HTTP validation hook | unset |
| `WORKFORCE_SERVICE_URL` | Future Workforce HTTP validation hook | unset |

`ADMIN_API_KEY` should be set only through environment or secret management. Do not commit it.

## Installation

```powershell
cd D:\netx\optiflow-ai\tools\incident-service
python -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install -r requirements.txt
```

## Running

```powershell
$env:DATABASE_URL='sqlite:///./data/incident.db'
$env:TOOL_SHARED_TOKEN='change-me'
$env:ADMIN_API_KEY='local-admin-key'
python -m uvicorn app.main:app --host 127.0.0.1 --port 8102
```

SQLite does not require a separate server installation. It stores the MVP database in `data/incident.db`; the service creates the parent directory automatically when the configured URL points to a SQLite file. Production deployments should use migrations rather than metadata table creation.

## Tests

Tests use isolated temporary SQLite databases and must not read or modify `data/incident.db`.

```powershell
python -m compileall app tests
python -m pytest -q
```

If Windows temp permissions are restricted, run pytest with `TMP` and `TEMP` pointed at a writable directory.

## Endpoints

| Method | Path | Auth | Purpose |
| --- | --- | --- | --- |
| `GET` | `/health` | none | Process health |
| `GET` | `/readiness` | none | Database readiness |
| `POST` | `/incident/api/v1/incidents` | `X-Tool-Token` | Create incident |
| `GET` | `/incident/api/v1/incidents` | `X-Tool-Token` | List incidents |
| `GET` | `/incident/api/v1/incidents/{incident_id}` | `X-Tool-Token` | Retrieve incident |
| `PATCH` | `/incident/api/v1/incidents/{incident_id}/status` | `X-Tool-Token` | Update lifecycle status |
| `POST` | `/incident/api/v1/incidents/{incident_id}/assign` | `X-Tool-Token` | Assign or reassign specialist |
| `POST` | `/admin/reset` | `X-Admin-Key` | Reset deterministic demo data |

Deprecated compatibility reads are also present for current core integration: `GET /escalations`, `GET /escalations/active`, and `GET /escalations/{escalation_id}`. They reuse Incident data and are marked deprecated in OpenAPI.

## Create Example

```json
{
  "incident_id": "INC-123",
  "customer_id": "CUS-ALPHA",
  "title": "Checkout latency spike",
  "description": "Checkout latency exceeded normal operating thresholds.",
  "priority": "high",
  "sla_deadline": "2099-08-01T10:00:00Z"
}
```

Successful responses use:

```json
{
  "success": true,
  "message": "Request completed successfully",
  "timestamp": "2026-07-24T10:00:00Z",
  "data": {}
}
```

Errors use:

```json
{
  "success": false,
  "message": "Incident not found",
  "errorCode": "INCIDENT_404",
  "timestamp": "2026-07-24T10:00:00Z"
}
```

## Priority Values

Accepted case-insensitive inputs are stored and returned as:

- `LOW`
- `MEDIUM`
- `HIGH`
- `CRITICAL`

Unknown values are rejected. The service does not silently downgrade unknown priorities.

## Status Values

Supported statuses:

- `OPEN`
- `IN_PROGRESS`
- `RESOLVED`
- `CLOSED`

New incidents start as `OPEN`. A create request may omit `status` or provide `OPEN`; other initial statuses are rejected.

Transition matrix:

| Current | Allowed next statuses |
| --- | --- |
| `OPEN` | `IN_PROGRESS`, `CLOSED` |
| `IN_PROGRESS` | `OPEN`, `RESOLVED`, `CLOSED` |
| `RESOLVED` | `IN_PROGRESS`, `CLOSED` |
| `CLOSED` | none |

Setting the current status again is idempotent and does not update `updated_at`.

## Listing

`GET /incident/api/v1/incidents` supports:

- `page`, default `1`
- `page_size`, default `20`, max `100`
- `status`
- `priority`
- `customer_id`
- `assigned_specialist_id`
- `unassigned`
- `overdue`
- `search`
- `sla_before`
- `sla_after`

Pagination and filtering happen in the database. Results are ordered by `sla_deadline` ascending, then `incident_id` ascending. `search` matches `incident_id`, `title`, or `description`.

An incident is overdue when `sla_deadline` is earlier than the current UTC time and status is neither `RESOLVED` nor `CLOSED`. Past SLA deadlines are allowed because imported or already-overdue incidents may exist.

## Assignment

`POST /incident/api/v1/incidents/{incident_id}/assign` accepts:

```json
{ "specialist_id": "SPEC-001" }
```

The endpoint stores the specialist reference only. It does not reserve Workforce capacity and does not directly read the Workforce database. Repeating the same assignment is idempotent. Reassignment is allowed while an incident is `OPEN` or `IN_PROGRESS`; `RESOLVED` and `CLOSED` incidents cannot be assigned.

## Customer References

`customer_id` is a logical reference to CRM. Part 3 validates the identifier format but does not call CRM and does not create a cross-database foreign key. Customer existence should be verified by the Core AI or a future integration layer unless the approved contract later requires synchronous CRM validation.

## Seed Data

Normal startup seeds only when the `incidents` table is empty. Reset replaces existing Incident rows with these deterministic demo records:

| Incident | Customer | Priority | Status | SLA | Specialist |
| --- | --- | --- | --- | --- | --- |
| `INC-ALPHA-001` | `CUS-ALPHA` | `CRITICAL` | `OPEN` | `2026-07-22T12:00:00Z` | unassigned |
| `INC-NOVA-001` | `CUS-NOVA` | `HIGH` | `IN_PROGRESS` | `2099-07-25T10:00:00Z` | `SPEC-NIMAL` |
| `INC-GREEN-001` | `CUS-GREEN` | `MEDIUM` | `OPEN` | `2099-07-27T10:00:00Z` | unassigned |
| `INC-MEDI-001` | `CUS-MEDI` | `LOW` | `RESOLVED` | `2026-07-23T10:00:00Z` | `SPEC-MAYA` |
| `INC-OMEGA-001` | `CUS-OMEGA` | `HIGH` | `CLOSED` | `2026-07-21T18:00:00Z` | `SPEC-DANIEL` |

## Error Codes

| Code | Meaning |
| --- | --- |
| `INCIDENT_401` | Invalid or missing credentials |
| `INCIDENT_404` | Incident not found |
| `INCIDENT_409` | Duplicate ID, invalid transition, or assignment conflict |
| `INCIDENT_422` | Request validation failed |
| `INCIDENT_500` | Unexpected internal error |
| `INCIDENT_503` | Database/configuration dependency failure |

## Security

The service validates all external input, rejects unknown request fields, avoids raw SQL assembled from user input, limits page size, hides database details from clients, avoids direct cross-service database access, and protects reset with an admin key. OpenAPI does not reveal configured credentials.

## MVP Limitations

- No optimistic concurrency version column is implemented yet; the MVP uses transactional last-write behavior.
- No incident audit-history table is exposed through the Part 3 API.
- CRM and Workforce references are logical only.
- Docker Compose does not currently pass `ADMIN_API_KEY`, so reset is disabled in Compose until that variable is configured.
- Core still uses older `/escalations/active`; deprecated compatibility reads remain until integration aligns on `/incident/api/v1/incidents`.

## PostgreSQL And Audit History

The database URL and async engine setup can accept PostgreSQL URLs later. Before production, add the approved migration tool, verify constraints/indexes against PostgreSQL, introduce managed credentials, and add audit-history or event tables for status and assignment changes instead of building a heavy event system in the MVP.
