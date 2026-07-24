# OptiFlow AI - Enterprise Services API Reference

## 1. Overview

Member 2 owns four independent FastAPI services for the Phase 2 MVP:

- CRM Service owns customer data.
- Incident Service owns incident lifecycle and assignment references.
- Workforce Service owns specialists, capacity, and reservations.
- Communication Service owns assignment requests and simulated notifications.

Each service owns its own database. Other systems must use REST APIs rather than reading service databases directly.

## 2. Base URLs

Local URLs:

- CRM: `http://localhost:8101`
- Incident: `http://localhost:8102`
- Workforce: `http://localhost:8103`
- Communication: `http://localhost:8104`

Docker internal URLs:

- `http://crm-service:8101`
- `http://incident-service:8102`
- `http://workforce-service:8103`
- `http://communication-service:8104`

## 3. Authentication

Business endpoints require `X-Tool-Token`. Admin reset endpoints require `X-Admin-Key`. Do not place real keys in source control, sample docs, logs, or screenshots.

## 4. Request Tracing

Clients may send `X-Request-ID`. Valid IDs are echoed in response headers. Missing or invalid IDs are replaced with a generated UUID. Request IDs are used for log correlation and are not added to JSON response bodies.

## 5. Standard Success Response

```json
{
  "success": true,
  "message": "Request completed successfully",
  "timestamp": "2026-07-24T10:00:00Z",
  "data": {}
}
```

## 6. Standard Error Response

```json
{
  "success": false,
  "message": "Safe public message",
  "errorCode": "CRM_404",
  "timestamp": "2026-07-24T10:00:00Z"
}
```

## 7. Common HTTP Status Codes

| Status | Meaning |
| --- | --- |
| `200` | Successful read, update, idempotent replay, reset, confirmation, or cancellation |
| `201` | Resource created |
| `401` | Missing or invalid service/admin credential |
| `404` | Requested resource not found |
| `409` | Duplicate identifier, lifecycle conflict, capacity conflict, or idempotency mismatch |
| `422` | Request validation failed |
| `500` | Unexpected service error with safe public message |
| `503` | Database/readiness/admin-reset configuration unavailable |

## 8. CRM Endpoints

All CRM business endpoints use `X-Tool-Token`.

| Method | Path | Purpose | Parameters | Body | Success | Important Errors | Idempotency | Related Service |
| --- | --- | --- | --- | --- | --- | --- | --- | --- |
| `GET` | `/health` | Process health | none | none | `200` status object | none expected | safe to retry | none |
| `GET` | `/readiness` | Database readiness | none | none | `200` readiness object | `503` | safe to retry | CRM DB |
| `GET` | `/crm/api/v1/customers` | List customers | `page`, `page_size`, `active`, `tier`, `search` | none | `200` with `customers`, `page`, `page_size`, `total_items`, `total_pages` | `401`, `422` | safe to retry | none |
| `GET` | `/crm/api/v1/customers/{customer_id}` | Retrieve one customer | `customer_id` path | none | `200` customer | `401`, `404`, `422` | safe to retry | none |
| `POST` | `/crm/api/v1/customers` | Create customer | none | `customer_id`, `name`, `tier`, `arr`, `renewal_date`, `active` | `201` customer | `401`, `409`, `422` | duplicate `customer_id` returns `409` | none |
| `PUT` | `/crm/api/v1/customers/{customer_id}` | Replace customer fields | `customer_id` path | `name`, `tier`, `arr`, `renewal_date`, `active` | `200` customer | `401`, `404`, `422` | same body can be retried | none |
| `POST` | `/admin/reset` | Reset deterministic CRM seed data | none | none | `200` seeded count | `401`, `503` | safe for demo reset only | CRM DB |

CRM customer fields: `customer_id`, `name`, `tier`, `arr`, `renewal_date`, `active`, `created_at`, `updated_at`.

Example success:

```json
{
  "success": true,
  "message": "Request completed successfully",
  "timestamp": "2026-07-24T10:00:00Z",
  "data": {
    "customer_id": "CUS-ALPHA",
    "name": "Alpha Bank",
    "tier": "Enterprise",
    "arr": "600000.00",
    "renewal_date": "2026-09-22",
    "active": true,
    "created_at": "2026-07-24T10:00:00Z",
    "updated_at": "2026-07-24T10:00:00Z"
  }
}
```

Example error:

```json
{
  "success": false,
  "message": "Customer not found",
  "errorCode": "CRM_404",
  "timestamp": "2026-07-24T10:00:00Z"
}
```

## 9. Incident Endpoints

All Incident business endpoints use `X-Tool-Token`.

| Method | Path | Purpose | Parameters | Body | Success | Important Errors | Idempotency | Related Service |
| --- | --- | --- | --- | --- | --- | --- | --- | --- |
| `GET` | `/health` | Process health | none | none | `200` status object | none expected | safe to retry | none |
| `GET` | `/readiness` | Database readiness | none | none | `200` readiness object | `503` | safe to retry | Incident DB |
| `POST` | `/incident/api/v1/incidents` | Create incident | none | `incident_id`, `customer_id`, `title`, `description`, `priority`, `sla_deadline`, optional `status`, optional `assigned_specialist_id` | `201` incident | `401`, `409`, `422` | duplicate `incident_id` returns `409` | CRM logical reference |
| `GET` | `/incident/api/v1/incidents` | List incidents | `page`, `page_size`, `status`, `priority`, `customer_id`, `assigned_specialist_id`, `unassigned`, `overdue`, `search`, `sla_before`, `sla_after` | none | `200` with incident list metadata | `401`, `422` | safe to retry | CRM and Workforce logical references |
| `GET` | `/incident/api/v1/incidents/{incident_id}` | Retrieve one incident | `incident_id` path | none | `200` incident | `401`, `404`, `422` | safe to retry | none |
| `PATCH` | `/incident/api/v1/incidents/{incident_id}/status` | Update lifecycle status | `incident_id` path | `status` | `200` incident | `401`, `404`, `409`, `422` | same status is idempotent | none |
| `POST` | `/incident/api/v1/incidents/{incident_id}/assign` | Store specialist assignment reference | `incident_id` path | `specialist_id` | `200` incident | `401`, `404`, `409`, `422` | same specialist is idempotent | Workforce logical reference |
| `POST` | `/admin/reset` | Reset deterministic Incident seed data | none | none | `200` seeded count | `401`, `503` | safe for demo reset only | Incident DB |

Incident fields: `incident_id`, `customer_id`, `title`, `description`, `priority`, `status`, `sla_deadline`, `assigned_specialist_id`, `created_at`, `updated_at`.

Example success:

```json
{
  "success": true,
  "message": "Incident created successfully",
  "timestamp": "2026-07-24T10:00:00Z",
  "data": {
    "incident_id": "INC-DEMO-001",
    "customer_id": "CUS-ALPHA",
    "title": "Checkout latency spike",
    "description": "Checkout latency exceeded thresholds.",
    "priority": "HIGH",
    "status": "OPEN",
    "sla_deadline": "2099-08-01T10:00:00Z",
    "assigned_specialist_id": null,
    "created_at": "2026-07-24T10:00:00Z",
    "updated_at": "2026-07-24T10:00:00Z"
  }
}
```

Example error:

```json
{
  "success": false,
  "message": "Invalid incident status transition",
  "errorCode": "INCIDENT_409",
  "timestamp": "2026-07-24T10:00:00Z"
}
```

## 10. Workforce Endpoints

All Workforce business endpoints use `X-Tool-Token`.

| Method | Path | Purpose | Parameters | Body | Success | Important Errors | Idempotency | Related Service |
| --- | --- | --- | --- | --- | --- | --- | --- | --- |
| `GET` | `/health` | Process health | none | none | `200` status object | none expected | safe to retry | none |
| `GET` | `/readiness` | Database readiness | none | none | `200` readiness object | `503` | safe to retry | Workforce DB |
| `GET` | `/workforce/api/v1/specialists` | List specialists | `page`, `page_size`, `active`, `availability`, `skill`, `min_available_capacity`, `search` | none | `200` with specialist list metadata | `401`, `422` | safe to retry | none |
| `GET` | `/workforce/api/v1/specialists/available` | List operationally available specialists | `skill`, `required_capacity`, `page`, `page_size` | none | `200` with specialist list metadata | `401`, `422` | safe to retry | none |
| `GET` | `/workforce/api/v1/specialists/{specialist_id}` | Retrieve one specialist | `specialist_id` path | none | `200` specialist | `401`, `404`, `422` | safe to retry | none |
| `POST` | `/workforce/api/v1/reservations` | Create pending reservation | none | `reservation_id`, `specialist_id`, `incident_id`, optional `expires_in_seconds` | `201` reservation | `401`, `404`, `409`, `422` | duplicate `reservation_id` returns `409` | Incident logical reference |
| `GET` | `/workforce/api/v1/reservations/{reservation_id}` | Retrieve reservation | `reservation_id` path | none | `200` reservation | `401`, `404`, `422` | safe to retry | none |
| `PATCH` | `/workforce/api/v1/reservations/{reservation_id}/confirm` | Confirm pending reservation | `reservation_id` path | none | `200` reservation | `401`, `404`, `409`, `422` | already confirmed is idempotent | none |
| `DELETE` | `/workforce/api/v1/reservations/{reservation_id}` | Cancel pending or release confirmed reservation | `reservation_id` path | none | `200` reservation | `401`, `404`, `422` | cancelled/expired is idempotent | none |
| `POST` | `/admin/reset` | Reset deterministic Workforce seed data | none | none | `200` counts | `401`, `503` | safe for demo reset only | Workforce DB |

Specialist fields: `specialist_id`, `name`, `email`, `skills`, `capacity`, `current_workload`, `availability`, `active`, `effective_workload`, `available_capacity`, `operationally_available`, `created_at`, `updated_at`.

Reservation fields: `reservation_id`, `specialist_id`, `incident_id`, `status`, `created_at`, `expires_at`, `confirmed_at`, `cancelled_at`, `updated_at`.

Example success:

```json
{
  "success": true,
  "message": "Reservation created successfully",
  "timestamp": "2026-07-24T10:00:00Z",
  "data": {
    "reservation_id": "RES-DEMO-001",
    "specialist_id": "SPEC-MAYA",
    "incident_id": "INC-DEMO-001",
    "status": "PENDING",
    "created_at": "2026-07-24T10:00:00Z",
    "expires_at": "2026-07-24T10:05:00Z",
    "confirmed_at": null,
    "cancelled_at": null,
    "updated_at": "2026-07-24T10:00:00Z"
  }
}
```

Example error:

```json
{
  "success": false,
  "message": "Specialist has no available capacity",
  "errorCode": "WORKFORCE_409",
  "timestamp": "2026-07-24T10:00:00Z"
}
```

## 11. Communication Endpoints

All Communication business endpoints use `X-Tool-Token`.

| Method | Path | Purpose | Parameters | Body | Success | Important Errors | Idempotency | Related Service |
| --- | --- | --- | --- | --- | --- | --- | --- | --- |
| `GET` | `/health` | Process health | none | none | `200` status object | none expected | safe to retry | none |
| `GET` | `/readiness` | Database readiness | none | none | `200` readiness object | `503` | safe to retry | Communication DB |
| `POST` | `/communication/api/v1/assignment-requests` | Create assignment request | none | `request_id`, `incident_id`, `specialist_id`, `message`, optional `expires_in_seconds` | `201` assignment request | `401`, `409`, `422` | duplicate `request_id` returns `409` | Incident and Workforce logical references |
| `GET` | `/communication/api/v1/assignment-requests` | List assignment requests | `page`, `page_size`, `status`, `incident_id`, `specialist_id`, `pending_only`, `expired`, `created_after`, `created_before`, `search` | none | `200` with assignment list metadata | `401`, `422` | safe to retry | none |
| `GET` | `/communication/api/v1/assignment-requests/{request_id}` | Retrieve one assignment request | `request_id` path | none | `200` assignment request | `401`, `404`, `422` | safe to retry | none |
| `POST` | `/communication/api/v1/assignment-requests/{request_id}/respond` | Accept or reject request | `request_id` path | `response`, optional `response_note` | `200` assignment request | `401`, `404`, `409`, `422` | same final response is idempotent | none |
| `POST` | `/communication/api/v1/notifications` | Create notification and simulate delivery | none | `notification_id`, `recipient`, `channel`, optional `subject`, `message`, optional `related_request_id`, optional `idempotency_key` | `201` created or `200` idempotent replay | `401`, `404`, `409`, `422` | same idempotency key and payload returns existing resource | Communication assignment reference |
| `GET` | `/communication/api/v1/notifications` | List notifications | `page`, `page_size`, `status`, `channel`, `recipient`, `related_request_id`, `created_after`, `created_before`, `search` | none | `200` with notification list metadata | `401`, `422` | safe to retry | none |
| `GET` | `/communication/api/v1/notifications/{notification_id}` | Retrieve one notification | `notification_id` path | none | `200` notification | `401`, `404`, `422` | safe to retry | none |
| `POST` | `/admin/reset` | Reset deterministic Communication seed data | none | none | `200` counts | `401`, `503` | safe for demo reset only | Communication DB |

Assignment request fields: `request_id`, `incident_id`, `specialist_id`, `message`, `status`, `created_at`, `expires_at`, `responded_at`, `response_note`, `updated_at`.

Notification fields: `notification_id`, `recipient`, `channel`, `subject`, `message`, `status`, `idempotency_key`, `related_request_id`, `created_at`, `attempted_at`, `delivered_at`, `failure_reason`, `attempt_count`, `updated_at`.

Example success:

```json
{
  "success": true,
  "message": "Notification created and delivered",
  "timestamp": "2026-07-24T10:00:00Z",
  "data": {
    "notification_id": "NOT-DEMO-001",
    "recipient": "maya.sen@example.test",
    "channel": "EMAIL",
    "subject": "New Incident Assignment",
    "message": "You have received an assignment request.",
    "status": "DELIVERED",
    "idempotency_key": "assignment-demo-email",
    "related_request_id": "AR-DEMO-001",
    "created_at": "2026-07-24T10:00:00Z",
    "attempted_at": "2026-07-24T10:00:00Z",
    "delivered_at": "2026-07-24T10:00:00Z",
    "failure_reason": null,
    "attempt_count": 1,
    "updated_at": "2026-07-24T10:00:00Z"
  }
}
```

Example error:

```json
{
  "success": false,
  "message": "Idempotency key was used with a different payload",
  "errorCode": "COMMUNICATION_409",
  "timestamp": "2026-07-24T10:00:00Z"
}
```

## 12. Pagination

List endpoints use `page` and `page_size`. Defaults are `page=1` and `page_size=20`. Current public API validation caps page size at `100`.

## 13. Filtering And Search

Filtering is service-specific and database-side where practical. Search fields are text-based and intended for operational demos, not full-text production search.

## 14. Enum Values

CRM tiers: `Standard`, `Premium`, `Enterprise`.

Incident priorities: `LOW`, `MEDIUM`, `HIGH`, `CRITICAL`.

Incident statuses: `OPEN`, `IN_PROGRESS`, `RESOLVED`, `CLOSED`.

Workforce reservation statuses: `PENDING`, `CONFIRMED`, `CANCELLED`, `EXPIRED`.

Communication assignment statuses: `PENDING`, `ACCEPTED`, `REJECTED`, `EXPIRED`, `CANCELLED`.

Communication response values: `ACCEPTED`, `REJECTED`.

Notification channels: `EMAIL`, `SMS`, `IN_APP`, `WEBHOOK`.

Notification statuses: `PENDING`, `DELIVERED`, `FAILED`.

## 15. Error-Code Catalogue

| Service | Codes |
| --- | --- |
| CRM | `CRM_401`, `CRM_404`, `CRM_409`, `CRM_422`, `CRM_500`, `CRM_503` |
| Incident | `INCIDENT_401`, `INCIDENT_404`, `INCIDENT_409`, `INCIDENT_422`, `INCIDENT_500`, `INCIDENT_503` |
| Workforce | `WORKFORCE_401`, `WORKFORCE_404`, `WORKFORCE_409`, `WORKFORCE_422`, `WORKFORCE_500`, `WORKFORCE_503` |
| Communication | `COMMUNICATION_401`, `COMMUNICATION_404`, `COMMUNICATION_409`, `COMMUNICATION_422`, `COMMUNICATION_500`, `COMMUNICATION_503` |

## 16. Idempotency Behavior

- Incident same-status update returns the current resource.
- Incident same-specialist assignment returns the current resource.
- Workforce already-confirmed reservation returns the current resource.
- Workforce repeated cancellation of cancelled or expired reservations returns the current resource.
- Communication repeated same final assignment response returns the current resource.
- Communication notification `idempotency_key` returns an existing notification when the payload matches.
- Communication notification `idempotency_key` with a different payload returns `COMMUNICATION_409`.

## 17. Reset Behavior

`POST /admin/reset` is a demo/admin operation. It requires `X-Admin-Key`, clears service-owned records in safe order, and restores deterministic seed data. It does not reset another service.

## 18. Health And Readiness

`/health` verifies the FastAPI process is responsive. `/readiness` verifies database reachability. Compose health checks use `/readiness`.

## 19. OpenAPI Documentation URLs

- CRM: `http://localhost:8101/docs`
- Incident: `http://localhost:8102/docs`
- Workforce: `http://localhost:8103/docs`
- Communication: `http://localhost:8104/docs`

Deprecated compatibility endpoints remain in selected services for older demo/core surfaces, but the versioned paths in this reference are the Member 2 handover contract.
