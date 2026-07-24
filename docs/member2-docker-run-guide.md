# Member 2 Docker Run Guide

## Docker Prerequisites

Install Docker with Compose support and ensure the daemon is running before using this guide.

Validate local tooling:

```powershell
docker --version
docker compose version
docker context ls
```

Part 7 validation on this machine confirmed the CLI exists but the Docker daemon endpoint was unavailable. Docker build and startup require that external environment issue to be fixed first.

## Environment Setup

Create a local `.env` from `.env.example` if desired. Do not commit `.env`.

Important non-secret defaults are already present in Compose. Replace placeholders locally:

```powershell
$env:TOOL_SHARED_TOKEN = "<your-local-tool-token>"
$env:ADMIN_API_KEY = "<your-local-admin-key>"
```

## Compose Configuration

Default Compose scope starts the four Member 2 enterprise services:

```powershell
cd D:\netx\optiflow-ai
docker compose config
docker compose config --services
```

Expected services:

- `crm-service`
- `incident-service`
- `workforce-service`
- `communication-service`

`postgres`, `core-api`, and `frontend` remain behind the `full-stack` profile.

## Build Images

```powershell
docker compose build
```

Each service image copies `shared/python`, installs the service requirements, installs `optiflow-shared`, copies only its own app, creates `/app/data`, and runs as a non-root `optiflow` user.

## Start Services

```powershell
docker compose up -d
```

## Inspect Containers

```powershell
docker compose ps
docker compose logs --tail=100 crm-service
docker compose logs --tail=100 incident-service
docker compose logs --tail=100 workforce-service
docker compose logs --tail=100 communication-service
```

Logs should contain structured request records and must not contain admin keys, tool tokens, database URLs with credentials, raw authorization headers, or full request bodies.

## Health Verification

```powershell
Invoke-RestMethod -Method Get -Uri "http://localhost:8101/health"
Invoke-RestMethod -Method Get -Uri "http://localhost:8102/health"
Invoke-RestMethod -Method Get -Uri "http://localhost:8103/health"
Invoke-RestMethod -Method Get -Uri "http://localhost:8104/health"
```

## Readiness Verification

```powershell
Invoke-RestMethod -Method Get -Uri "http://localhost:8101/readiness"
Invoke-RestMethod -Method Get -Uri "http://localhost:8102/readiness"
Invoke-RestMethod -Method Get -Uri "http://localhost:8103/readiness"
Invoke-RestMethod -Method Get -Uri "http://localhost:8104/readiness"
```

Compose health checks also use `/readiness`.

## Run Integration Tests Against Local Services

The current integration tests start their own subprocess services by default. For Docker-based manual validation, use the API samples against the exposed ports or extend the test harness with explicit base URLs after team approval.

```powershell
.\tools\crm-service\.venv\Scripts\python.exe -m pytest integration-tests -q
```

## Restart One Service

```powershell
docker compose restart crm-service
docker compose logs --tail=50 crm-service
```

## Stop Services

Preserve volumes:

```powershell
docker compose down
```

Warning: `docker compose down -v` deletes named volumes and erases local SQLite data. Use it only when you intentionally want a clean local data reset.

## Rebuild After Dependency Changes

```powershell
docker compose build --no-cache crm-service
docker compose up -d crm-service
```

Repeat per service when requirements or shared package files change.

## Service Ports

| Service | Host Port | Container Port |
| --- | --- | --- |
| CRM | `8101` | `8101` |
| Incident | `8102` | `8102` |
| Workforce | `8103` | `8103` |
| Communication | `8104` | `8104` |

## Internal Service URLs

- `http://crm-service:8101`
- `http://incident-service:8102`
- `http://workforce-service:8103`
- `http://communication-service:8104`

## Volume Design

Each service has its own named `/app/data` volume:

- `crm_data`
- `incident_data`
- `workforce_data`
- `communication_data`

No service mounts or reads another service database.

## Common Docker Problems

Docker daemon unavailable: start Docker Desktop or the configured Docker engine, then rerun `docker compose build`.

Wrong Docker context: inspect `docker context ls` and switch to the context with a running daemon.

Port conflict: stop the process using `8101` through `8104` or override the published port in `.env`.

Image uses stale dependencies: rebuild the affected service with `--no-cache`.

Service unhealthy: run `docker compose logs <service>` and call `/readiness` from the host.

Missing admin key: set `ADMIN_API_KEY` locally before reset workflows.

SQLite path issue: verify the named volume is mounted at `/app/data` and the container user owns it.

## SQLite Production Limitation

This Compose setup is for MVP and demo usage. It is not production-ready. SQLite is not suitable for horizontally scaled multi-writer deployments. Production should use PostgreSQL, managed migrations, secrets management, centralized logging, and a production authentication boundary.
