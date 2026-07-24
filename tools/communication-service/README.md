# OptiFlow Communication Service

The Communication Service owns assignment-request and notification workflow records for OptiFlow AI Phase 2. It records requests sent to specialists, captures accept/reject responses, creates notifications, and simulates delivery outcomes for demos and tests.

It does not choose the specialist, assign incidents, reserve Workforce capacity, send real messages, or call real providers. Core AI and approved workflows make decisions; this service records and communicates them through REST APIs.

## Architecture

The service is a FastAPI application using SQLAlchemy 2.x async ORM, Pydantic v2, SQLite for the MVP, and pytest.

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
  services/assignment_service.py
  services/delivery_service.py
  services/failure_service.py
  services/notification_service.py
  config.py
  main.py
```

## Environment

| Variable | Purpose | Default |
| --- | --- | --- |
| `SERVICE_NAME` | Service metadata | `communication-service` |
| `SERVICE_PORT` | Runtime port | `8104` |
| `DATABASE_URL` | SQLAlchemy database URL | `sqlite:///./data/communication.db` |
| `TOOL_SHARED_TOKEN` | Required as `X-Tool-Token` on Communication APIs | `change-me` |
| `ADMIN_API_KEY` | Required as `X-Admin-Key` on `POST /admin/reset` | unset |
| `ASSIGNMENT_REQUEST_TTL_SECONDS` | Default pending assignment TTL | `900` |
| `MIN_ASSIGNMENT_REQUEST_TTL_SECONDS` | Minimum accepted TTL | `30` |
| `MAX_ASSIGNMENT_REQUEST_TTL_SECONDS` | Maximum accepted TTL | `86400` |
| `SIMULATED_DELIVERY_MODE` | `success`, `fail`, or `recipient_rule` | `success` |
| `SEED_ON_STARTUP` | Seed when assignment table is empty | `true` |
| `INCIDENT_SERVICE_URL` | Future Incident validation hook | unset |
| `WORKFORCE_SERVICE_URL` | Future Workforce validation hook | unset |

Do not commit real admin keys, provider credentials, real recipient lists, or `.env` files.

## Installation

```powershell
cd D:\netx\optiflow-ai\tools\communication-service
python -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install -r requirements.txt
```

## Running

```powershell
$env:DATABASE_URL='sqlite:///./data/communication.db'
$env:TOOL_SHARED_TOKEN='change-me'
$env:ADMIN_API_KEY='local-admin-key'
$env:SIMULATED_DELIVERY_MODE='recipient_rule'
python -m uvicorn app.main:app --host 127.0.0.1 --port 8104
```

SQLite is file-based and does not require a separate database server. The service creates the SQLite parent directory automatically only for SQLite file URLs. Production deployments should use migrations rather than metadata table creation.

## Tests

Tests use isolated temporary SQLite databases and must not touch `data/communication.db`.

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
| `POST` | `/communication/api/v1/assignment-requests` | `X-Tool-Token` | Create pending assignment request |
| `GET` | `/communication/api/v1/assignment-requests` | `X-Tool-Token` | List assignment requests |
| `GET` | `/communication/api/v1/assignment-requests/{request_id}` | `X-Tool-Token` | Retrieve one assignment request |
| `POST` | `/communication/api/v1/assignment-requests/{request_id}/respond` | `X-Tool-Token` | Accept or reject request |
| `POST` | `/communication/api/v1/notifications` | `X-Tool-Token` | Create notification and simulate delivery |
| `GET` | `/communication/api/v1/notifications` | `X-Tool-Token` | List notifications |
| `GET` | `/communication/api/v1/notifications/{notification_id}` | `X-Tool-Token` | Retrieve one notification |
| `POST` | `/admin/reset` | `X-Admin-Key` | Reset deterministic demo data |

Deprecated compatibility endpoints remain for current demo/core integration: `/assignment-requests`, `/assignment-requests/{request_id}`, `/assignment-requests/{request_id}/respond`, `/notifications`, `/notifications/{notification_id}`, `/admin/next-response`, and `/admin/failure-mode`.

## Request Examples

Create assignment request:

```json
{
  "request_id": "AR-001",
  "incident_id": "INC-001",
  "specialist_id": "SPEC-001",
  "message": "Please review and accept this incident assignment.",
  "expires_in_seconds": 900
}
```

Respond:

```json
{
  "response": "ACCEPTED",
  "response_note": "I am available to handle this incident."
}
```

Create notification:

```json
{
  "notification_id": "NOT-001",
  "recipient": "specialist@example.test",
  "channel": "EMAIL",
  "subject": "New Incident Assignment",
  "message": "You have received a new incident assignment request.",
  "related_request_id": "AR-001",
  "idempotency_key": "assignment-AR-001-email"
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

Error envelope:

```json
{
  "success": false,
  "message": "Assignment request not found",
  "errorCode": "COMMUNICATION_404",
  "timestamp": "2026-07-24T10:00:00Z"
}
```

## Assignment Requests

Fields: `request_id`, `incident_id`, `specialist_id`, `message`, `status`, `created_at`, `expires_at`, `responded_at`, `response_note`, and `updated_at`. Internal numeric IDs are not exposed.

Statuses:

- `PENDING`
- `ACCEPTED`
- `REJECTED`
- `EXPIRED`
- `CANCELLED`

`PENDING` requests can be accepted or rejected until `expires_at`. `ACCEPTED`, `REJECTED`, `EXPIRED`, and `CANCELLED` are final states. Repeating the same final response returns the stored result unchanged and preserves the original response note. An opposite response after a final response returns `COMMUNICATION_409`.

Expiration is lazy: expired pending requests are normalized to `EXPIRED` during list, get, and respond operations. No background scheduler is used in the MVP.

## Notifications

Fields: `notification_id`, `recipient`, `channel`, `subject`, `message`, `status`, `idempotency_key`, `related_request_id`, `created_at`, `attempted_at`, `delivered_at`, `failure_reason`, `attempt_count`, and `updated_at`.

Channels:

- `EMAIL`
- `SMS`
- `IN_APP`
- `WEBHOOK`

Statuses:

- `PENDING`
- `DELIVERED`
- `FAILED`

Recipient validation is intentionally simple for the MVP. Email recipients must contain one `@` and have text on both sides. SMS recipients must use `+` followed by 8 to 15 digits. In-app and webhook recipients are non-empty identifiers or destinations. Email notifications require a subject.

`idempotency_key` prevents duplicate notification creation. A replay with the same key and same payload returns the existing notification with HTTP 200. Reusing the same key with a different payload returns `COMMUNICATION_409`. Duplicate `notification_id` also returns `COMMUNICATION_409`.

## Simulated Delivery

No real email, SMS, in-app message, or webhook request is sent.

Delivery modes:

- `success`: every notification is marked `DELIVERED`.
- `fail`: every notification is marked `FAILED`.
- `recipient_rule`: recipients containing `fail` are marked `FAILED`; all others are `DELIVERED`.

Every delivery attempt increments `attempt_count` and sets `attempted_at`. Successful simulated delivery sets `delivered_at` and clears `failure_reason`. Expected simulated failure preserves the notification, sets `FAILED`, stores a controlled reason, and still returns 201 because the resource was created.

## Listing And Filters

Assignment requests support `page`, `page_size`, `status`, `incident_id`, `specialist_id`, `pending_only`, `expired`, `created_after`, `created_before`, and `search`.

Notifications support `page`, `page_size`, `status`, `channel`, `recipient`, `related_request_id`, `created_after`, `created_before`, and `search`.

Page size is capped at 100. Assignment requests order by `created_at` descending, then `request_id`. Notifications order by `created_at` descending, then `notification_id`.

## Cross-Service References

`incident_id` is a logical Incident Service reference. `specialist_id` is a logical Workforce Service reference. Communication does not import Incident or Workforce models, open their databases, or create cross-service foreign keys. `related_request_id` is validated within the Communication database when supplied for notifications.

## Seed Data

Startup seeds only when the assignment table is empty. Reset inserts:

| Assignment | Incident | Specialist | Status |
| --- | --- | --- | --- |
| `AR-PENDING-001` | `INC-ALPHA-001` | `SPEC-MAYA` | `PENDING` |
| `AR-ACCEPTED-001` | `INC-NOVA-001` | `SPEC-DANIEL` | `ACCEPTED` |
| `AR-REJECTED-001` | `INC-MEDI-001` | `SPEC-NIMAL` | `REJECTED` |
| `AR-EXPIRED-001` | `INC-EXPIRED-001` | `SPEC-PRIYA` | expired `PENDING`, lazily normalized |
| `AR-CANCELLED-001` | `INC-CANCELLED-001` | `SPEC-KAI` | `CANCELLED` |

| Notification | Channel | Recipient | Status | Related request |
| --- | --- | --- | --- | --- |
| `NOT-EMAIL-DELIVERED` | `EMAIL` | `maya.sen@example.test` | `DELIVERED` | `AR-PENDING-001` |
| `NOT-SMS-DELIVERED` | `SMS` | `+15550101010` | `DELIVERED` | `AR-ACCEPTED-001` |
| `NOT-INAPP-DELIVERED` | `IN_APP` | `SPEC-DANIEL` | `DELIVERED` | `AR-ACCEPTED-001` |
| `NOT-FAILED-001` | `EMAIL` | `fail@example.test` | `FAILED` | `AR-REJECTED-001` |
| `NOT-WEBHOOK-DELIVERED` | `WEBHOOK` | `webhook-demo-destination` | `DELIVERED` | none |

## Error Codes

| Code | Meaning |
| --- | --- |
| `COMMUNICATION_401` | Invalid or missing credentials |
| `COMMUNICATION_404` | Missing assignment request, notification, or related request |
| `COMMUNICATION_409` | Duplicate ID, idempotency mismatch, opposite response, or lifecycle conflict |
| `COMMUNICATION_422` | Validation failure |
| `COMMUNICATION_500` | Unexpected internal error |
| `COMMUNICATION_503` | Database or reset configuration failure |

## Security And Limits

The service validates input, rejects unknown fields on new write APIs, limits page sizes, hides database/provider errors, avoids raw SQL interpolation, does not expose secrets, protects reset with `X-Admin-Key`, and avoids returning internal numeric IDs.

## SQLite And PostgreSQL

SQLite is suitable for the MVP and local demos, but it is not a production-grade multi-instance concurrency database. The service uses uniqueness constraints, transactional commits, and idempotency checks, but production PostgreSQL should add migrations, row-level locking or optimistic version columns for assignment responses, and stronger transactional handling around idempotency keys.

Future asynchronous delivery should use an approved queue, retry schedule, dead-letter handling, provider-specific adapters, delivery audit trails, and secret-managed provider credentials.
