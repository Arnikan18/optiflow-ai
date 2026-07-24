# Member 2 Local Run Guide

## Required Python Version

Use Python 3.11 or newer. The current validation used the existing CRM virtual environment. Python 3.13 may need updated wheels for some packages in clean environments, so prefer Python 3.11 or 3.12 for least friction.

## Repository Location

```powershell
cd D:\netx\optiflow-ai
```

## Virtual Environment

Create and activate a virtual environment. The existing repository currently has one under `tools/crm-service\.venv`; a fresh setup can use one venv per service or one shared developer venv.

```powershell
cd D:\netx\optiflow-ai\tools\crm-service
python -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install -r requirements.txt
python -m pip install -e ..\..\shared\python
```

For Incident, Workforce, and Communication, either install their matching requirements into the same venv or create service-local venvs. Their declared dependency stack is currently aligned with CRM.

## Common Environment Variables

Use placeholders for local secrets.

```powershell
$env:TOOL_SHARED_TOKEN = "<your-local-tool-token>"
$env:ADMIN_API_KEY = "<your-local-admin-key>"
$env:LOG_LEVEL = "INFO"
$env:ENABLE_SEED_DATA = "true"
$env:REQUEST_ID_HEADER = "X-Request-ID"
$env:MAX_REQUEST_ID_LENGTH = "128"
$env:MAX_PAGE_SIZE = "100"
```

## Run CRM On 8101

```powershell
cd D:\netx\optiflow-ai\tools\crm-service
$env:SERVICE_NAME = "crm-service"
$env:SERVICE_PORT = "8101"
$env:DATABASE_URL = "sqlite:///./data/crm.db"
.\.venv\Scripts\python.exe -m uvicorn app.main:app --host 127.0.0.1 --port 8101
```

Health: `http://localhost:8101/health`

Readiness: `http://localhost:8101/readiness`

OpenAPI: `http://localhost:8101/docs`

## Run Incident On 8102

```powershell
cd D:\netx\optiflow-ai\tools\incident-service
$env:PYTHONPATH = "D:\netx\optiflow-ai\shared\python"
$env:SERVICE_NAME = "incident-service"
$env:SERVICE_PORT = "8102"
$env:DATABASE_URL = "sqlite:///./data/incident.db"
..\crm-service\.venv\Scripts\python.exe -m uvicorn app.main:app --host 127.0.0.1 --port 8102
```

Health: `http://localhost:8102/health`

Readiness: `http://localhost:8102/readiness`

OpenAPI: `http://localhost:8102/docs`

## Run Workforce On 8103

```powershell
cd D:\netx\optiflow-ai\tools\workforce-service
$env:PYTHONPATH = "D:\netx\optiflow-ai\shared\python"
$env:SERVICE_NAME = "workforce-service"
$env:SERVICE_PORT = "8103"
$env:DATABASE_URL = "sqlite:///./data/workforce.db"
$env:RESERVATION_TTL_SECONDS = "300"
..\crm-service\.venv\Scripts\python.exe -m uvicorn app.main:app --host 127.0.0.1 --port 8103
```

Health: `http://localhost:8103/health`

Readiness: `http://localhost:8103/readiness`

OpenAPI: `http://localhost:8103/docs`

## Run Communication On 8104

```powershell
cd D:\netx\optiflow-ai\tools\communication-service
$env:PYTHONPATH = "D:\netx\optiflow-ai\shared\python"
$env:SERVICE_NAME = "communication-service"
$env:SERVICE_PORT = "8104"
$env:DATABASE_URL = "sqlite:///./data/communication.db"
$env:ASSIGNMENT_REQUEST_TTL_SECONDS = "900"
$env:SIMULATED_DELIVERY_MODE = "success"
..\crm-service\.venv\Scripts\python.exe -m uvicorn app.main:app --host 127.0.0.1 --port 8104
```

Health: `http://localhost:8104/health`

Readiness: `http://localhost:8104/readiness`

OpenAPI: `http://localhost:8104/docs`

## Run Unit Tests

CRM:

```powershell
cd D:\netx\optiflow-ai\tools\crm-service
$env:PYTHONPATH = "D:\netx\optiflow-ai\shared\python"
.\.venv\Scripts\python.exe -m compileall app tests
.\.venv\Scripts\python.exe -m pytest tests -q
```

Incident:

```powershell
cd D:\netx\optiflow-ai\tools\incident-service
$env:PYTHONPATH = "D:\netx\optiflow-ai\shared\python"
..\crm-service\.venv\Scripts\python.exe -m compileall app tests
..\crm-service\.venv\Scripts\python.exe -m pytest tests -q -p no:cacheprovider
```

Workforce:

```powershell
cd D:\netx\optiflow-ai\tools\workforce-service
$env:PYTHONPATH = "D:\netx\optiflow-ai\shared\python"
..\crm-service\.venv\Scripts\python.exe -m compileall app tests
..\crm-service\.venv\Scripts\python.exe -m pytest tests -q
```

Communication:

```powershell
cd D:\netx\optiflow-ai\tools\communication-service
$env:PYTHONPATH = "D:\netx\optiflow-ai\shared\python"
..\crm-service\.venv\Scripts\python.exe -m compileall app tests
..\crm-service\.venv\Scripts\python.exe -m pytest tests -q
```

## Run Shared Tests

```powershell
cd D:\netx\optiflow-ai
$env:PYTHONPATH = "D:\netx\optiflow-ai\shared\python"
.\tools\crm-service\.venv\Scripts\python.exe -m pytest shared\python\tests -q
```

## Run Integration Tests

The integration tests start all four services on temporary localhost ports, use isolated SQLite files, call REST APIs only, and tear down the subprocesses after the run.

```powershell
cd D:\netx\optiflow-ai
$env:PYTHONPATH = "D:\netx\optiflow-ai\shared\python"
.\tools\crm-service\.venv\Scripts\python.exe -m pytest integration-tests -q
```

## Troubleshooting

Port already in use: choose a different port for local manual runs, or stop the process currently using `8101` through `8104`.

Virtual environment not activated: call the venv Python executable explicitly, as shown in the commands.

Module import failure: install the shared package with `python -m pip install -e ..\..\shared\python` or set `PYTHONPATH` to `D:\netx\optiflow-ai\shared\python`.

SQLite path issue: verify the parent `data` directory is writable, or use a temp SQLite URL such as `sqlite:///D:/netx/tmp/crm.db`.

Missing `ADMIN_API_KEY`: reset endpoints return `503` when admin reset is not configured and `401` when the supplied key is wrong.

Invalid `DATABASE_URL`: use `sqlite:///./data/<service>.db` for local MVP runs. Async services convert SQLite URLs internally.

Python 3.13 package-build issue: create a Python 3.11 or 3.12 virtual environment and reinstall requirements.

Service not ready: call `/readiness`, inspect the Uvicorn console output, and confirm the database URL is writable.

Database locked: stop duplicate local service processes using the same SQLite file, wait for the lock to clear, then retry.

Existing local database state: use `POST /admin/reset` with `X-Admin-Key` to restore deterministic seed data. Do not delete local files as a first step.
