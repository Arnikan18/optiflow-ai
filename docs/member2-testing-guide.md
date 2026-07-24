# Member 2 Testing Guide

## Test Architecture

Member 2 tests are split into:

- Service unit/API tests under each service `tests` directory.
- Shared-package tests under `shared/python/tests`.
- Integration tests under `integration-tests`.

Integration tests use REST APIs against live Uvicorn subprocesses and never read another service database.

## Unit Tests

CRM:

```powershell
cd D:\netx\optiflow-ai\tools\crm-service
$env:PYTHONPATH = "D:\netx\optiflow-ai\shared\python"
.\.venv\Scripts\python.exe -m compileall app tests
.\.venv\Scripts\python.exe -m pytest tests -q
```

Expected Part 7 result: `15 passed`.

Incident:

```powershell
cd D:\netx\optiflow-ai\tools\incident-service
$env:PYTHONPATH = "D:\netx\optiflow-ai\shared\python"
..\crm-service\.venv\Scripts\python.exe -m compileall app tests
..\crm-service\.venv\Scripts\python.exe -m pytest tests -q -p no:cacheprovider
```

Expected Part 7 result: `18 passed`.

Workforce:

```powershell
cd D:\netx\optiflow-ai\tools\workforce-service
$env:PYTHONPATH = "D:\netx\optiflow-ai\shared\python"
..\crm-service\.venv\Scripts\python.exe -m compileall app tests
..\crm-service\.venv\Scripts\python.exe -m pytest tests -q
```

Expected Part 7 result: `27 passed`.

Communication:

```powershell
cd D:\netx\optiflow-ai\tools\communication-service
$env:PYTHONPATH = "D:\netx\optiflow-ai\shared\python"
..\crm-service\.venv\Scripts\python.exe -m compileall app tests
..\crm-service\.venv\Scripts\python.exe -m pytest tests -q
```

Expected Part 7 result: `21 passed`.

## Shared-Package Tests

```powershell
cd D:\netx\optiflow-ai
$env:PYTHONPATH = "D:\netx\optiflow-ai\shared\python"
.\tools\crm-service\.venv\Scripts\python.exe -m compileall shared\python\optiflow_shared
.\tools\crm-service\.venv\Scripts\python.exe -m pytest shared\python\tests -q
```

Expected Part 7 result: `7 passed`.

## Integration Tests

```powershell
cd D:\netx\optiflow-ai
$env:PYTHONPATH = "D:\netx\optiflow-ai\shared\python"
.\tools\crm-service\.venv\Scripts\python.exe -m pytest integration-tests -q
```

Expected Part 7 result: `3 passed`.

The integration suite starts all four services on temporary ports, waits for readiness, resets each service with an admin key, runs the end-to-end workflow, verifies request IDs, runs negative tests, and terminates every subprocess.

## Docker-Based Tests

Compose syntax:

```powershell
docker compose config --services
```

Expected default services:

- `crm-service`
- `incident-service`
- `workforce-service`
- `communication-service`

Image build:

```powershell
docker compose build
```

Part 7 environment result: blocked because the Docker daemon endpoint was unavailable at `npipe:////./pipe/dockerDesktopLinuxEngine`.

## Test Database Isolation

Unit tests use pytest temporary SQLite databases. Integration tests use temporary SQLite files created under pytest's temp area. Tests do not use committed `data/*.db` files and do not read another service's database.

## Reset Endpoint Use

Integration tests call each service's `POST /admin/reset` with a test-only admin key before each workflow. Reset is service-local and deterministic.

## Request-ID Testing

Shared tests verify request-ID sanitization and middleware behavior. Integration tests verify the same `X-Request-ID` is returned on success and controlled error responses across all four services.

## End-To-End Workflow

The integration workflow verifies:

1. CRM customer retrieval.
2. Incident creation.
3. Workforce available-specialist listing.
4. Workforce reservation creation.
5. Incident specialist assignment.
6. Communication assignment-request creation.
7. Assignment acceptance.
8. Workforce reservation confirmation.
9. Incident status update to `IN_PROGRESS`.
10. Communication notification creation and idempotent replay.
11. Final retrieval of customer, incident, specialist, reservation, assignment request, and notification.

## Negative Tests

The integration suite covers missing records, duplicate identifiers, invalid incident transition, capacity conflict, duplicate active reservation, expired reservation confirm, opposite final response, notification idempotency replay, idempotency payload conflict, invalid admin key on every reset endpoint, invalid request data, and request-ID headers on errors.

## Repeated-Run Testing

Part 7 ran the integration suite twice in sequence:

- First run: `3 passed`.
- Second run: `3 passed`.

This validates test isolation and repeatability.

## Troubleshooting Failures

Import failure: ensure `PYTHONPATH` includes `D:\netx\optiflow-ai\shared\python` or install the shared package editable.

Incident pytest cache permission error: rerun with `-p no:cacheprovider`. This avoids writing `.pytest_cache` in a restricted folder and does not change service behavior.

Port conflict in integration tests: the harness allocates free ports automatically. If a subprocess still runs after interruption, stop it before rerunning.

Docker build failure: verify a running Docker daemon before debugging Dockerfiles.

Database locked: stop duplicate local Uvicorn instances using the same SQLite file.

Member 1 failure signal: failures in core orchestration, frontend calls, AI planning, or cross-team API sequencing belong outside Member 2 unless the failing request violates this API reference.

Member 2 failure signal: failures in the four service APIs, response wrappers, service-owned data, reset, request-ID behavior, or Member 2 integration tests belong to Member 2.
