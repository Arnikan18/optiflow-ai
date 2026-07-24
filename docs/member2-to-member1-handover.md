# Member 2 to Member 1 Handover

## 1. What Member 2 Completed

Member 2 completed CRM, Incident, Workforce, Communication, shared technical standards, integration tests, Docker/Compose configuration, API documentation, sample data documentation, local run guidance, Docker guidance, and testing guidance.

## 2. Service Base URLs

- CRM: `http://localhost:8101`
- Incident: `http://localhost:8102`
- Workforce: `http://localhost:8103`
- Communication: `http://localhost:8104`

## 3. Docker Internal Service URLs

- `http://crm-service:8101`
- `http://incident-service:8102`
- `http://workforce-service:8103`
- `http://communication-service:8104`

## 4. Service Health And Readiness URLs

- CRM: `/health`, `/readiness`
- Incident: `/health`, `/readiness`
- Workforce: `/health`, `/readiness`
- Communication: `/health`, `/readiness`

## 5. OpenAPI Documentation URLs

- CRM: `http://localhost:8101/docs`
- Incident: `http://localhost:8102/docs`
- Workforce: `http://localhost:8103/docs`
- Communication: `http://localhost:8104/docs`

## 6. Required Environment Variables

Core integration needs service base URLs and `TOOL_SHARED_TOKEN`. Demo reset workflows need `ADMIN_API_KEY`. Do not commit either value.

## 7. CRM Capabilities

CRM can list, retrieve, create, update, seed, and reset customer records. It owns `customer_id`, `name`, `tier`, `arr`, `renewal_date`, `active`, `created_at`, and `updated_at`.

## 8. Incident Capabilities

Incident can create, list, retrieve, transition, assign, seed, and reset incident records. It owns incident lifecycle state and stores customer/specialist IDs as logical references.

## 9. Workforce Capabilities

Workforce can list specialists, filter available specialists, retrieve specialists, create reservations, confirm reservations, cancel or release reservations, seed, and reset.

## 10. Communication Capabilities

Communication can create/list/retrieve assignment requests, accept or reject requests, create/list/retrieve notifications, simulate delivery, seed, and reset.

## 11. Standard Response Wrapper

All versioned service APIs use:

```json
{"success": true, "message": "...", "timestamp": "...Z", "data": {}}
```

## 12. Standard Error Wrapper

Controlled errors use:

```json
{"success": false, "message": "...", "errorCode": "SERVICE_CODE", "timestamp": "...Z"}
```

## 13. Request-ID Behavior

Send `X-Request-ID` on every call. Valid values are echoed in response headers and appear in structured request logs. Do not expect `requestId` in JSON bodies.

## 14. Important Error Codes

- CRM: `CRM_401`, `CRM_404`, `CRM_409`, `CRM_422`, `CRM_500`, `CRM_503`
- Incident: `INCIDENT_401`, `INCIDENT_404`, `INCIDENT_409`, `INCIDENT_422`, `INCIDENT_500`, `INCIDENT_503`
- Workforce: `WORKFORCE_401`, `WORKFORCE_404`, `WORKFORCE_409`, `WORKFORCE_422`, `WORKFORCE_500`, `WORKFORCE_503`
- Communication: `COMMUNICATION_401`, `COMMUNICATION_404`, `COMMUNICATION_409`, `COMMUNICATION_422`, `COMMUNICATION_500`, `COMMUNICATION_503`

## 15. Recommended Core AI Workflow

Core AI should orchestrate the workflow. Member 2 services do not perform automatic cross-service side effects.

## 16. API Call Order

1. Retrieve CRM customer context.
2. Create or retrieve Incident.
3. Find available Workforce specialists.
4. Create reservation.
5. Assign specialist to Incident.
6. Create Communication assignment request.
7. Receive accept/reject response.
8. Confirm or cancel reservation.
9. Update Incident status.
10. Send simulated notification.
11. Monitor and replan when needed.

## 17. Idempotency Rules

Same Incident status and same Incident specialist assignment are idempotent. Already confirmed Workforce reservations are idempotent. Repeated Workforce cancellation of terminal reservations is idempotent. Repeated same Communication response is idempotent. Communication notification idempotency uses `idempotency_key`.

## 18. Retry Guidance

Retry safe reads, same-status updates, same assignment, already-confirmed reservation confirmation, and notification creation with the same idempotency key and same payload. Do not blindly retry conflicting writes with different identifiers.

## 19. Timeout Guidance

Use short service timeouts for MVP integration, such as 2 to 5 seconds per call. Treat timeout as unknown state for writes and use read/idempotency checks before retrying.

## 20. Failure Handling Guidance

On `401`, check credentials. On `404`, re-check IDs. On `409`, replan or fetch current state. On `422`, fix request shape. On `503`, wait or check service readiness.

## 21. Demo Reset Procedure

Reset in this human-friendly order: CRM, Incident, Workforce, Communication. Every reset uses only the target service database.

## 22. Integration-Test Command

```powershell
cd D:\netx\optiflow-ai
$env:PYTHONPATH = "D:\netx\optiflow-ai\shared\python"
.\tools\crm-service\.venv\Scripts\python.exe -m pytest integration-tests -q
```

## 23. Known MVP Limitations

SQLite is used for local MVP storage. Communication is simulated. No queue, retry worker, real provider, distributed tracing backend, rate limiting, or production auth system is implemented.

## 24. PostgreSQL Migration Recommendation

Move to PostgreSQL before production or multi-instance writes. Add migrations, row-level locking or optimistic versioning, managed secrets, backups, and production observability.

## 25. Information Member 1 Must Not Assume

- Do not access service databases directly.
- Do not assume a reservation is confirmed before calling confirm.
- Do not assume assignment request acceptance automatically updates Incident or Workforce.
- Do not assume Communication sends real messages.
- Do not assume SQLite supports horizontal write scaling.
- Do not assume service IDs are database foreign keys across services.

## 26. Remaining Team Decisions

Decide production auth, migration tooling, whether core should consume only versioned APIs, provider strategy for real communications, queue/retry architecture, and observability stack.

## 27. Member 2 Completion Status

Member 2 implementation and Python validation are complete. Docker runtime validation remains blocked until a Docker daemon is available in the local environment.
