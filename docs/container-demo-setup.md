# OptiFlow Container Demo Setup

The complete demonstration runs in Docker:

| Service | Local address |
| --- | --- |
| Frontend | <http://localhost:3000> |
| Core API | <http://localhost:8000> |
| CRM | <http://localhost:8101> |
| Incident | <http://localhost:8102> |
| Workforce | <http://localhost:8103> |
| Communication | <http://localhost:8104> |
| PostgreSQL | `localhost:5432` |

The frontend is served by Nginx. Node.js is not required on the demo laptop.

## New Windows laptop

Install Git and Docker Desktop, start Docker Desktop, then run:

```powershell
git clone https://github.com/Arnikan18/optiflow-ai.git
cd optiflow-ai
git checkout demo
powershell -ExecutionPolicy Bypass -File .\scripts\start-demo.ps1 -Fresh -Force
```

Open <http://localhost:3000>.

## New macOS or Linux laptop

Install Git and Docker Desktop or Docker Engine with Compose v2, then run:

```bash
git clone https://github.com/Arnikan18/optiflow-ai.git
cd optiflow-ai
git checkout demo
chmod +x scripts/start-demo.sh scripts/reset-demo.sh
./scripts/start-demo.sh --fresh --force
```

Open <http://localhost:3000>.

## What the fresh command creates

The startup command:

1. Creates `.env` from `.env.example` when it is missing.
2. Removes only the Docker containers and volumes owned by this Compose project.
3. Builds and starts PostgreSQL, the four enterprise services, Core, and the frontend.
4. Loads the version-controlled rich customer, incident, workforce, performance, capacity, reservation, and communication data.
5. Seeds mature SLA-first manager preference history.
6. Waits for every application health check to pass.

No external LLM key is required for the deterministic demonstration. Provider keys can remain empty.

## Daily commands

Stop all OptiFlow containers but keep their databases:

```powershell
docker compose --profile full-stack down
```

Start them again without rebuilding:

```powershell
docker compose --profile full-stack up -d --wait
```

Rebuild after pulling code:

```powershell
docker compose --profile full-stack up -d --build --wait
```

Show container status:

```powershell
docker compose --profile full-stack ps
```

Follow all logs:

```powershell
docker compose --profile full-stack logs -f
```

Follow only Core and frontend logs:

```powershell
docker compose --profile full-stack logs -f core-api frontend
```

Reset enterprise data without deleting the containers:

```powershell
powershell -ExecutionPolicy Bypass -File .\scripts\reset-demo.ps1
```

Restore mature SLA-first preference history:

```powershell
docker compose --profile full-stack exec -T core-api python -m scripts.seed_preference_demo --profile SLA_FIRST --apply
```

Create a completely fresh seeded demonstration again:

```powershell
powershell -ExecutionPolicy Bypass -File .\scripts\start-demo.ps1 -Fresh -Force
```

## Data portability

The baseline is generated from committed scenario files and seed code, not copied from one laptop's private database files. A fresh setup therefore recreates the same rich presentation data on another laptop.

Decisions made after startup live in local Docker volumes. They are intentionally not committed or automatically transferred to another laptop. Run the fresh startup command there to reproduce the approved baseline.
