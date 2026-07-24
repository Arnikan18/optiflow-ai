# Member 2 Repository Audit

## 1. Audit date and branch

- Audit date: 2026-07-24
- Repository path: `D:\netx\optiflow-ai`
- Current branch during audit: `sanjeevan`
- `git branch --show-current` returned `sanjeevan`.
- `git log --oneline --left-right develop...sanjeevan` returned no commits, so local `develop` and current `sanjeevan` had no local divergence at audit time.
- Important branch risk: refs with both `Sanjeevan` and `sanjeevan` exist. `refs/heads/sanjeevan` points at `8a094be`, while `origin/sanjeevan` pointed at `3341936` before the Part 1 push. `origin/Sanjeevan` and `origin/main` pointed at `8a094be`.
- Important integration risk: local `develop` and `origin/develop` were divergent at audit time. `origin/develop...develop` showed local `develop` had `8a094be` and `3812b28`, while `origin/develop` had `83fc793` and `c79c1e7`.

## 2. Repository summary

Existing working functionality:

- The repository is an OptiFlow AI Phase 2 codebase with root `README.md`, `.env.example`, `.gitignore`, `docker-compose.yml`, `database/init.sql`, `core-api`, `shared`, `scenarios`, and four tool-service folders.
- `docker-compose.yml` defines the expected seven containers: frontend, core-api, CRM, Incident, Workforce, Communication, and PostgreSQL.
- Tool services are configured as separate containers with separate SQLite database volumes.
- PostgreSQL is configured for core decision data.

Existing incomplete functionality:

- No tracked frontend folder exists even though `docker-compose.yml` references `./frontend`.
- Root README is minimal and does not contain build, test, API, or architecture guidance.
- Architecture and API contract documents are not tracked in the repository beyond partial shared schema files and scenario data.

Missing functionality:

- No tracked service tests were found.
- No tool database migrations were found.
- No complete API contract document was found.
- No existing `AGENTS.md` or equivalent permanent agent instruction file was found before this audit.

## 3. Member 2 ownership

Member 2 owns:

- `tools/crm-service`
- `tools/incident-service`
- `tools/workforce-service`
- `tools/communication-service`

Shared code may be touched only when it is genuinely shared by these services. `core-api`, `frontend`, AI agent code, Member 1 code, Member 3 code, and approved architecture decisions should not be modified without explicit permission.

## 4. Current Git state

Existing working functionality:

- Remote `origin` exists and points to `https://github.com/Arnikan18/optiflow-ai.git`.
- Local branches found: `Sanjeevan`, `develop`, `main`; the current symbolic ref is `refs/heads/sanjeevan`.
- Remote branches found: `origin/Arnikan`, `origin/Sanjeevan`, `origin/develop`, `origin/main`, `origin/sanjeevan`.
- No existing merge conflict markers or detached HEAD state were found.

Existing incomplete or risky state:

- `docs/part1.md` and `docs/part2.md` were untracked during the audit. They were not staged by this Part 1 work.
- Ignored local artifacts exist under CRM, including `tools/crm-service/.venv`, `tools/crm-service/data/crm.db`, and Python cache files.
- Local and remote develop histories are divergent. A strict `git pull --ff-only origin develop` is expected to fail unless the branch relationship changes.

## 5. CRM service status

Existing working functionality:

- Folder exists at `tools/crm-service`.
- Dockerfile exists and runs `uvicorn app.main:app` on port `8101`.
- Requirements include FastAPI, Uvicorn, Pydantic v2, SQLAlchemy, aiosqlite, httpx, pytest, and pytest-asyncio.
- Config file exists with environment-based settings fields.
- SQLAlchemy model `Customer` exists.
- Pydantic response schema `CustomerResponse` exists.
- Request-ID middleware and token authentication helper files exist.
- Local seed logic exists for three hardcoded customers.

Existing incomplete functionality:

- The FastAPI entry point is currently inconsistent. `app/main.py` imports `router` from `app.api.routes`, but `app/api/routes.py` defines a separate `FastAPI` app and no `router` object.
- `app/api/routes.py` duplicates root and health app definitions instead of exposing an `APIRouter`.
- `app/api/admin_routes.py`, `app/services/domain_service.py`, and `app/schemas/requests.py` are empty.
- Middleware and authentication helpers exist but are not wired into the CRM app.
- The database session uses a hardcoded `sqlite:///./data/crm.db` instead of `settings.database_url`.
- CRM uses synchronous SQLAlchemy while the other three tool services use async SQLAlchemy.
- `app/services/failure_service.py` imports a `FailureMode` model that does not exist in CRM models and expects `AsyncSession`, which does not match CRM's sync database setup.
- Seed data does not use the shared Phase 2 scenario IDs or fields.

Missing functionality:

- No verified `/customers` endpoint exists, despite core expecting `GET /customers`.
- No verified `/customers/{customer_id}` endpoint exists.
- No verified commercial dependency endpoint exists.
- No admin reset or failure-mode endpoint is wired.
- No tests exist in `tools/crm-service/tests`.
- No service/repository layer is implemented.
- No readiness endpoint separate from `/health` was found.

Contradictions with architecture:

- Database URL is not configuration-driven.
- Service is not currently a valid FastAPI service as wired.
- CRM seed/model shape does not match the Version 4 scenario data.
- Failure-mode and request-context components are present but not integrated.

## 6. Incident service status

Existing working functionality:

- Folder exists at `tools/incident-service`.
- It is an async FastAPI service with entry point `app.main:app`.
- Dockerfile runs on port `8102`.
- Database URL comes from configuration and maps `sqlite:///` to `sqlite+aiosqlite:///`.
- Models exist for `Escalation`, `EscalationSkill`, `EscalationAccess`, `AssignmentHistory`, `IncidentEvent`, and `FailureMode`.
- Seed/reset logic loads `scenarios/phase2-demo.json`.
- Request-ID middleware and token authentication are wired into protected endpoints.
- Health endpoint checks database reachability.
- Routes found: `GET /escalations`, `GET /escalations/active`, `GET /escalations/{escalation_id}`, `POST /escalations/{escalation_id}/assign`, `POST /escalations/{escalation_id}/status`, `POST /admin/escalations`, `POST /admin/escalations/{escalation_id}/sla-change`, `POST /admin/escalations/{escalation_id}/workaround`, `POST /admin/failure-mode`, and `POST /admin/reset`.
- Assignment writes include an idempotency-key lookup against `AssignmentHistory`.

Existing incomplete functionality:

- Routes, business logic, validation, and persistence are concentrated in `app/main.py`.
- Request payloads are untyped `dict` values rather than Pydantic request schemas.
- Response payloads are manually assembled dictionaries rather than documented response schemas.
- There is no separate service or repository layer.
- Date-time values are stored as strings.
- `get_db` commits after the route finishes but does not explicitly rollback on route exceptions.
- Assignment IDs and assignment references use random values, which weakens reproducibility.

Missing functionality:

- No tests were found.
- No pagination or filters were found on list endpoints.
- No readiness endpoint separate from `/health` was found.
- No explicit status transition validation was found.
- No explicit guard blocks assignment of closed or resolved incidents.

## 7. Workforce service status

Existing working functionality:

- Folder exists at `tools/workforce-service`.
- It is an async FastAPI service with entry point `app.main:app`.
- Dockerfile runs on port `8103`.
- Database URL comes from configuration and maps `sqlite:///` to `sqlite+aiosqlite:///`.
- Models exist for `Specialist`, `SpecialistSkill`, `SpecialistAccess`, `AvailabilitySlot`, `WorkloadRecord`, `Reservation`, and `FailureMode`.
- Seed/reset logic loads `scenarios/phase2-demo.json`.
- Request-ID middleware and token authentication are wired into protected endpoints.
- Health endpoint checks database reachability.
- Routes found: `GET /specialists`, `GET /specialists/{specialist_id}`, `GET /availability`, `GET /workload`, `POST /reservations/tentative`, `POST /reservations/{reservation_id}/confirm`, `DELETE /reservations/{reservation_id}`, `POST /admin/specialists/{specialist_id}/unavailable`, `POST /admin/specialists/{specialist_id}/capacity`, `POST /admin/workload/{specialist_id}`, `POST /admin/failure-mode`, and `POST /admin/reset`.
- Tentative reservations and notifications include idempotency-key lookup where implemented.

Existing incomplete functionality:

- Routes, business logic, validation, and persistence are concentrated in `app/main.py`.
- Request payloads are untyped `dict` values rather than Pydantic request schemas.
- Response payloads are manually assembled dictionaries.
- There is no separate service or repository layer.
- Date-time values are stored as strings.
- `get_db` commits after the route finishes but does not explicitly rollback on route exceptions.
- Reservation IDs use random values, which weakens reproducibility and duplicate handling.
- Tentative reservation creation verifies that the specialist exists but does not fully enforce active status, working window, existing reservations, or capacity.
- Reservation confirmation increments workload but does not guard already confirmed reservations.

Missing functionality:

- No tests were found.
- No pagination or filters were found on list endpoints.
- No readiness endpoint separate from `/health` was found.
- No explicit expired-reservation handling was found.
- No concurrency-safe over-capacity prevention was found.

## 8. Communication service status

Existing working functionality:

- Folder exists at `tools/communication-service`.
- It is an async FastAPI service with entry point `app.main:app`.
- Dockerfile runs on port `8104`.
- Database URL comes from configuration and maps `sqlite:///` to `sqlite+aiosqlite:///`.
- Models exist for `AssignmentRequest`, `Notification`, `ConfiguredResponse`, and `FailureMode`.
- Seed/reset logic loads configured responses from `scenarios/phase2-demo.json`.
- Request-ID middleware and token authentication are wired into protected endpoints.
- Health endpoint checks database reachability.
- Routes found: `POST /assignment-requests`, `GET /assignment-requests/{request_id}`, `POST /assignment-requests/{request_id}/respond`, `POST /notifications`, `GET /notifications/{notification_id}`, `POST /admin/next-response`, `POST /admin/failure-mode`, and `POST /admin/reset`.
- Assignment request and notification creation support idempotency-key lookup.
- Configured delayed specialist responses are simulated with background tasks.

Existing incomplete functionality:

- Routes, business logic, validation, and persistence are concentrated in `app/main.py`.
- Request payloads are untyped `dict` values rather than Pydantic request schemas.
- Response payloads are manually assembled dictionaries.
- There is no separate service or repository layer.
- Date-time values are stored as strings.
- `get_db` commits after the route finishes but does not explicitly rollback on route exceptions.
- Request IDs and notification IDs use random values.
- `respond_to_request` does not prevent answering the same request more than once.
- Status values are not restricted to accepted communication enums.

Missing functionality:

- No tests were found.
- No readiness endpoint separate from `/health` was found.
- No list endpoint for `GET /assignment-requests` was found, although `core-api` currently calls that path in `/api/demo/portfolio`.
- No request expiration behavior was found.
- No simulated notification delivery failure path was found beyond service-level failure modes.

## 9. Shared code status

Existing working functionality:

- Shared Python files exist under `shared/python/optiflow_shared`.
- Shared TypeScript files exist under `shared/typescript`.
- Shared enums include freshness, failure mode, escalation status, and assignment request status.
- Shared errors include a basic error envelope and standard error-code constants.
- Shared tool contract includes `ToolResponseEnvelope`.
- Shared identifiers define stable customer, escalation, and specialist IDs.
- Shared policy JSON files exist.

Existing incomplete functionality:

- `shared/python/optiflow_shared/events.py` is empty.
- Shared Python contracts do not yet define full request and response models for the four tool services.
- Shared TypeScript contracts are partial and do not fully reflect the current service endpoints.

## 10. Existing API contract status

Existing working functionality:

- Partial TypeScript API and model interfaces are present.
- Partial Python enums and error contracts are present.
- Tool-service routes can be discovered from code.

Existing incomplete functionality:

- No complete tracked API contract document was found.
- Service responses do not consistently use the shared `ToolResponseEnvelope`.
- Current endpoint alignment issues exist:
  - `core-api` calls CRM `GET /customers`, but CRM does not currently expose it.
  - `core-api` calls Communication `GET /assignment-requests`, but Communication exposes only create, get-by-id, and respond endpoints.
  - CRM has `app/api/routes.py` shaped as a FastAPI app rather than an APIRouter.

## 11. Database strategy found in the repository

Existing working functionality:

- `database/init.sql` initializes core PostgreSQL tables for schema versions, users, agent runs, run events, and tool calls.
- Compose gives each tool service a separate SQLite database path and persistent Docker volume.
- Incident, Workforce, and Communication use environment-provided database URLs and async SQLAlchemy engines.
- Tool service model classes use SQLAlchemy 2 style.

Existing incomplete functionality:

- CRM hardcodes `sqlite:///./data/crm.db` and does not use the configured `DATABASE_URL`.
- Tool services rely on `Base.metadata.create_all` rather than migrations.
- Tool date-time values are stored as strings, not typed date-time columns.
- Foreign-key relationships are not explicitly modeled in the tool services.
- Important lookup indexes are limited; most models rely only on primary keys and idempotency uniqueness.
- SQLite-to-PostgreSQL migration would require cleanup around string timestamps, transaction handling, constraints, and schema validation.

## 12. Test status

Existing working functionality:

- pytest and pytest-asyncio are listed in service requirements.
- `tools/crm-service/tests` exists but contains no test files.

Missing functionality:

- No tracked test files were found anywhere in the repository.
- No pytest configuration file was found.
- No service-specific test commands were documented in README or service docs.

Validation commands run during Part 1:

- `python -X utf8 -c "... ast.parse ..."` over all `tools/*-service/app/**/*.py`: passed, 47 service Python files parsed.
- `rg --files -g '*test*' -g '*tests*'`: found no tracked test files.
- `python -m pytest --version`: failed because the global Python environment did not have pytest installed.
- `.\.venv\Scripts\python.exe -m pytest --collect-only -q` from `tools/crm-service`: ran with CRM's ignored local virtual environment; no tests were collected.
- Incident, Workforce, and Communication pytest runs were skipped because no service-local virtual environments were present, the global Python environment lacked pytest, and no tracked tests existed.

Recommended test command for each service once tests exist:

- `python -m pytest` from the relevant service directory.

## 13. Docker and deployment status

Existing working functionality:

- `docker-compose.yml` defines services for PostgreSQL, four tool services, core-api, and frontend.
- Tool service Dockerfiles install dependencies, copy `app`, create `/app/data`, and run Uvicorn on the expected ports.
- Compose mounts shared Python contracts and scenario data into tool containers.
- Compose defines health checks for PostgreSQL and all four tool services.

Existing incomplete functionality:

- The `frontend` directory referenced by Compose does not exist in the current tracked tree.
- CRM is likely unable to start because `app.main` imports a missing `router`.
- Compose mounts tool app directories into containers, so local source state can override image contents during development.

## 14. Configuration and environment-variable status

Existing working functionality:

- `.env.example` defines app, core, PostgreSQL, tool URLs, tool ports, shared token, timeout, retry, and demo settings.
- Each service has an `app/config.py` with `BaseSettings`.
- Incident, Workforce, and Communication read database URLs from environment.
- Tool shared token is configurable.

Existing incomplete functionality:

- CRM does not use `settings.database_url` for its database session.
- Required service settings have no defaults except `scenario_id`, so local direct imports need environment variables.
- No startup validation wrapper was found to present missing configuration as a consistent service error.

## 15. Scalability observations

- The agreed database-per-service boundary is represented in Docker Compose.
- Incident, Workforce, and Communication are closer to the desired future PostgreSQL migration path than CRM because they use configuration-driven SQLAlchemy URLs.
- Monolithic `main.py` implementations should be split into API route modules, Pydantic schema modules, service/domain logic, and repositories before adding much more behavior.
- Random operational IDs should become deterministic or collision-resistant identifiers with unique constraints.
- List endpoints need pagination and filters before scenario size grows.
- String timestamps should be replaced or normalized through a common timezone-aware handling approach.
- Transaction helpers should rollback on failure and centralize commit behavior.

## 16. Security and validation observations

Existing working functionality:

- Protected endpoints in Incident, Workforce, and Communication use `X-Tool-Token`.
- Request-ID middleware attaches and returns `X-Request-ID` in Incident, Workforce, and Communication.
- `.gitignore` excludes `.env`, local databases, virtual environments, caches, and logs.

Existing incomplete functionality:

- CRM auth and request-ID middleware exist but are not wired into the app.
- Unstructured `dict` payloads allow missing fields, invalid enum values, wrong types, and excessive strings to reach business logic.
- Errors use plain `HTTPException` details rather than the shared error envelope.
- Some health endpoints expose raw database exception text.
- There is no centralized redaction or logging policy in the tool services.

## 17. Edge cases that future parts must handle

General:

- Missing required fields
- Empty strings
- Invalid enum values
- Extremely long strings
- Negative numeric values
- Invalid dates
- Past deadlines where inappropriate
- Duplicate identifiers
- Missing records
- Inactive records
- Concurrent updates
- Retried requests
- Database errors
- Partial transaction failures
- Invalid pagination values
- Excessively large page sizes
- Unsupported filters
- Malformed JSON
- Service-unavailable conditions
- Configuration variables missing at startup

CRM:

- Duplicate customer ID
- Negative ARR
- Inactive customer
- Invalid customer tier
- Invalid renewal date
- Updating a missing customer
- Missing commercial dependency customer
- Scenario seed mismatch

Incident:

- Duplicate incident ID
- Invalid priority
- Invalid severity
- Invalid status transition
- Assigning an already assigned incident
- Assigning a closed or resolved incident
- Missing customer reference
- Expired SLA deadline
- Duplicate idempotency key with mismatched payload

Workforce:

- Missing specialist
- Inactive specialist
- Specialist unavailable
- Workload equal to or above capacity
- Duplicate reservation
- Expired reservation
- Confirming an already confirmed reservation
- Releasing or cancelling a missing reservation
- Concurrent reservations causing over-capacity
- Reservation outside available slot
- Negative or zero reservation duration

Communication:

- Duplicate assignment request
- Answering the same request twice
- Invalid accept/reject status
- Expired assignment request
- Missing recipient
- Invalid communication channel
- Simulated delivery failure
- Duplicate notification caused by retries
- Duplicate idempotency key with mismatched payload

## 18. Contradictions, risks, and uncertainties

Contradictions:

- CRM is not currently aligned with the agreed service architecture because its entry point imports a missing router and its database URL is hardcoded.
- Core expects endpoints that are missing in CRM and Communication.
- Compose references a missing `frontend` folder.
- `origin/develop` and local `develop` are divergent, which conflicts with a simple fast-forward integration workflow.

Risks:

- Case drift between `Sanjeevan` and `sanjeevan` can confuse branch operations on different platforms.
- Random IDs can create collisions and make tests or demos non-reproducible.
- Unvalidated dict payloads can allow silent bad state.
- Startup seed resets all tool data, which is good for demos but risky if later reused outside controlled MVP scenarios.
- Lack of tests means current service behavior is not protected during Part 2 changes.

Uncertainties requiring confirmation:

- Whether `origin/develop` or local `develop` should be the authoritative integration base.
- Whether the uppercase `Sanjeevan` branch should remain.
- Whether `docs/part1.md` and `docs/part2.md` should be retained, removed, ignored, or committed by a human in a separate change.
- Whether CRM should be repaired in place or replaced with the async pattern used by the other three services during Part 2.

## 19. Recommended implementation order

1. Resolve Git branch authority before merging additional implementation work: decide how to reconcile local `develop`, `origin/develop`, `Sanjeevan`, and `sanjeevan`.
2. Stabilize CRM startup without changing business scope: fix the missing APIRouter issue, wire request context and token authentication, and move database URL to configuration.
3. Align CRM data model and seed data with the shared Phase 2 scenario.
4. Add Pydantic request and response schemas for all four services.
5. Add missing contract endpoints used by core or adjust core only with explicit approval from the team.
6. Introduce small repository/service layers for one service at a time.
7. Add pytest coverage around health, reset, core read paths, writes, idempotency, and failure modes.
8. Tighten validation, error envelopes, transaction rollback, and timestamp handling.
9. Add pagination/filter scaffolding for list endpoints.
10. Add concurrency and capacity protections for Workforce reservations.

## 20. Part 2 readiness checklist

- [x] Repository structure inspected.
- [x] Git branch state inspected.
- [x] Member 2 service folders inspected.
- [x] Docker, configuration, shared contracts, scenario data, and tests inspected.
- [x] Current gaps documented without implementing functionality.
- [x] Permanent agent instructions added.
- [ ] Branch authority issue resolved by the team.
- [ ] CRM startup issue fixed.
- [ ] Tests added for each service.
- [ ] API contract alignment confirmed with Member 1 and Member 3.
- [ ] Missing `/customers` and `/assignment-requests` contract mismatch resolved.
- [ ] Part 2 implementation started only after Part 1 is reviewed.
