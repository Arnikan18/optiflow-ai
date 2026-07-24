# OptiFlow AI Coding Agent Instructions

## Project Purpose

OptiFlow AI Phase 2 is a human-governed autonomous portfolio decision system for B2B SaaS customer escalations. The Phase 2 MVP coordinates CRM, Incident, Workforce, and Communication tools through REST APIs while the core decision service owns portfolio reasoning, approval, execution orchestration, audit, and replanning.

## Member 2 Ownership

Member 2 owns the enterprise tool services:

- CRM Service: `tools/crm-service`, port `8101`
- Incident Service: `tools/incident-service`, port `8102`
- Workforce Service: `tools/workforce-service`, port `8103`
- Communication Service: `tools/communication-service`, port `8104`

Member 2 work may modify:

- `tools/crm-service`
- `tools/incident-service`
- `tools/workforce-service`
- `tools/communication-service`
- Shared components only when they are genuinely shared by these services
- Member 2 documentation files

Do not modify without explicit approval:

- `core-api`
- `frontend`
- AI agent implementation
- Member 1 or Member 3 owned code
- Approved architecture decisions

## Required Stack

- Python
- FastAPI
- SQLAlchemy 2.x
- Pydantic v2
- SQLite for the Phase 2 MVP
- PostgreSQL-compatible persistence design for future migration
- pytest
- REST APIs with JSON
- Environment-based configuration

## Service Boundaries

- Each tool service must remain independently deployable.
- Each service owns its own database.
- One service must never directly read or write another service's database.
- Cross-service communication must happen through APIs.
- The core service must call tool APIs rather than bypassing tool-owned SQLite data.
- Tool writes must be idempotent where retries are expected.

## Architecture Expectations

- Keep API routes, business logic, schemas, configuration, and persistence concerns separated.
- Avoid hardcoded URLs, ports, credentials, database paths, and secrets.
- Keep SQLite-specific assumptions close to database setup code.
- Prefer clear repository/service interfaces so SQLite can later be replaced with PostgreSQL.
- Add pagination and filters to list endpoints where the API surface can grow.
- Keep the MVP simple; do not introduce unnecessary distributed-system complexity.

## Edge-Case Expectations

Future implementation should explicitly handle:

- Missing required fields, empty strings, invalid enum values, invalid dates, duplicate identifiers, missing records, inactive records, malformed JSON, invalid pagination, oversized page sizes, unsupported filters, database errors, partial transaction failures, concurrent updates, retried requests, and missing configuration at startup.
- CRM-specific cases such as duplicate customer IDs, negative ARR, inactive customers, invalid tiers, invalid renewal dates, and updates to missing customers.
- Incident-specific cases such as duplicate incident IDs, invalid priorities, invalid status transitions, already assigned incidents, closed or resolved incidents, missing customer references, and expired SLA deadlines.
- Workforce-specific cases such as missing specialists, inactive or unavailable specialists, workload at or above capacity, duplicate or expired reservations, already confirmed reservations, missing reservation cancellation, and concurrent reservations that exceed capacity.
- Communication-specific cases such as duplicate assignment requests, repeated responses, invalid accept/reject statuses, expired requests, missing recipients, invalid channels, simulated delivery failure, and duplicate notifications from retries.

## Security and Validation

- Validate inbound payloads with Pydantic models before business logic runs.
- Return consistent error responses that do not expose stack traces, secrets, tokens, or internal implementation details.
- Use the shared tool token for protected service endpoints.
- Preserve request IDs on responses and include run IDs in logs when provided.
- Do not commit `.env`, local databases, virtual environments, credentials, tokens, private keys, caches, or generated artifacts.

## Testing Requirements

- Add or update focused pytest coverage with service changes.
- Include route, schema, repository, reset/seed, idempotency, validation, and failure-mode coverage as relevant.
- Run relevant tests after each small change.
- Do not fix unrelated failing tests as part of unrelated feature work; document them.

## Git Workflow

- Use `develop` as the integration base.
- Do Member 2 work on the `sanjeevan` branch.
- Stage only intended files.
- Use clear, scoped commits.
- Push `sanjeevan` before merging into `develop`.
- Merge into `develop` only after review, validation, and a clean intended diff.

## Small-Change Rule

- Create or modify only one or two logically connected files at a time.
- Inspect files before editing.
- Run relevant checks after each small change.
- Do not combine unrelated refactoring with feature work.
- Preserve existing working code unless the user explicitly approves a replacement.

## Destructive-Action Rules

Do not run destructive Git commands unless the user explicitly requests and confirms the exact operation. Prohibited by default:

- `git reset --hard`
- `git clean -fd`
- `git push --force`
- `git checkout -- .`
- `git restore .`
- `git branch -D`

If a merge conflict occurs, stop immediately and report every conflicting file. Do not guess a resolution.

## Documentation and Reporting

- Explain what changed, why it was needed, and whether it affects runtime behavior.
- Document existing incomplete functionality separately from implemented functionality.
- Do not claim a feature exists unless it was verified in the code or by tests.
