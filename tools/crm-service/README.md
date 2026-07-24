# OptiFlow CRM Service

The CRM Service owns customer business data used by OptiFlow AI during Phase 2 portfolio decisions. It exposes customer identity, tier, annual recurring revenue, renewal date, and active status through REST APIs. Other services must call the CRM API; they must not read the CRM SQLite database directly.

## Architecture

The service runs as an independent FastAPI application on port `8101`.

```text
app/
  api/routes.py
  database/base.py
  database/models.py
  database/seed.py
  database/session.py
  schemas/requests.py
  schemas/responses.py
  services/customer_service.py
  config.py
  main.py
```

- `api/routes.py`: HTTP endpoints and response conversion.
- `services/customer_service.py`: customer business logic, transactions, filtering, and reset.
- `schemas/`: Pydantic v2 request and response validation.
- `database/`: SQLAlchemy 2.x model, session, and deterministic seed data.
- `config.py`: environment-based settings.

## Stack

- Python
- FastAPI
- SQLAlchemy 2.x
- Pydantic v2
- SQLite for the MVP
- pytest
- Uvicorn

## Environment

| Variable | Purpose | Default |
| --- | --- | --- |
| `SERVICE_NAME` | Service metadata | `crm-service` |
| `SERVICE_PORT` | Service port | `8101` |
| `ENVIRONMENT` | Runtime environment label | `development` |
| `DATABASE_URL` | SQLAlchemy database URL | `sqlite:///./data/crm.db` |
| `LOG_LEVEL` | Structured log threshold | `INFO` |
| `TOOL_SHARED_TOKEN` | Required for customer API calls via `X-Tool-Token` | `change-me` |
| `ADMIN_API_KEY` | Required for `POST /admin/reset` via `X-Admin-Key` | unset |
| `SCENARIO_ID` | Demo scenario identifier | `phase2-demo` |
| `ENABLE_SEED_DATA` | Standard seed toggle alias | unset |
| `SEED_ON_STARTUP` | Seed when customer table is empty | `true` |
| `REQUEST_ID_HEADER` | Request correlation header | `X-Request-ID` |
| `MAX_REQUEST_ID_LENGTH` | Maximum accepted request ID length | `128` |
| `MAX_PAGE_SIZE` | Standard maximum page size | `100` |

SQLite is embedded in Python through the standard `sqlite3` runtime and SQLAlchemy. No separate SQLite server is required. The service creates the SQLite parent directory automatically only for SQLite URLs.

## Install And Run

```powershell
cd D:\netx\optiflow-ai\tools\crm-service
python -m venv .venv
.\.venv\Scripts\python.exe -m pip install -r requirements.txt
.\.venv\Scripts\python.exe -m pip install -e ..\..\shared\python

$env:DATABASE_URL='sqlite:///./data/crm.db'
$env:TOOL_SHARED_TOKEN='change-me'
$env:ADMIN_API_KEY='local-admin-key'
.\.venv\Scripts\python.exe -m uvicorn app.main:app --host 0.0.0.0 --port 8101
```

## Tests

Tests use an isolated temporary SQLite database and do not read or write `data/crm.db`.

```powershell
cd D:\netx\optiflow-ai\tools\crm-service
.\.venv\Scripts\python.exe -m compileall app tests
.\.venv\Scripts\python.exe -m pytest -q
```

## Endpoints

| Method | Path | Auth | Purpose |
| --- | --- | --- | --- |
| `GET` | `/health` | none | Process health |
| `GET` | `/readiness` | none | Database readiness |
| `GET` | `/crm/api/v1/customers` | `X-Tool-Token` | List customers |
| `GET` | `/crm/api/v1/customers/{customer_id}` | `X-Tool-Token` | Get one customer |
| `POST` | `/crm/api/v1/customers` | `X-Tool-Token` | Create customer |
| `PUT` | `/crm/api/v1/customers/{customer_id}` | `X-Tool-Token` | Update customer |
| `POST` | `/admin/reset` | `X-Admin-Key` | Reset deterministic CRM seed data |

## Pagination And Filtering

`GET /crm/api/v1/customers` supports:

- `page`: default `1`, minimum `1`
- `page_size`: default `20`, range `1..100`
- `active`: optional boolean
- `tier`: optional `Standard`, `Premium`, or `Enterprise`, case-insensitive
- `search`: optional customer ID/name search

Results are ordered by `customer_id` and paginated in the database.

## Request Example

```json
{
  "customer_id": "cus-example",
  "name": "Example Customer",
  "tier": "enterprise",
  "arr": "100000.00",
  "renewal_date": "2026-10-01",
  "active": true
}
```

Customer IDs are trimmed and stored uppercase. Tiers are stored as `Standard`, `Premium`, or `Enterprise`. Unknown fields are rejected.

## Response Example

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

## Error Codes

| Code | Meaning |
| --- | --- |
| `CRM_401` | Missing or invalid service/admin credential |
| `CRM_404` | Customer not found |
| `CRM_409` | Duplicate customer identifier |
| `CRM_422` | Validation error |
| `CRM_500` | Unexpected CRM service error |
| `CRM_503` | Database/configuration unavailable |

Error responses do not expose stack traces, SQL statements, connection strings, or API keys.

## Seed And Reset

Startup creates tables and seeds only when the customer table is empty. Normal startup does not overwrite existing records.

Seed records:

- `CUS-ALPHA`, Alpha Bank, Enterprise, `600000.00`, active
- `CUS-NOVA`, Nova Retail, Enterprise, `1200000.00`, active
- `CUS-GREEN`, GreenLogistics, Standard, `180000.00`, active
- `CUS-MEDI`, MediCore, Premium, `400000.00`, active
- `CUS-DORMANT`, Dormant Systems, Standard, `25000.00`, inactive

`POST /admin/reset` deletes CRM customers and reinserts the deterministic seed set in one transaction. It is disabled safely when `ADMIN_API_KEY` is not configured.

## Security Notes

- Customer endpoints require `X-Tool-Token`.
- Reset requires `X-Admin-Key`.
- Responses echo valid `X-Request-ID` values in the response header for log correlation.
- Do not commit `.env`, local databases, tokens, credentials, or virtual environments.
- Seed data is fictional and contains no sensitive personal data.

## MVP Limitations

- SQLAlchemy metadata creates tables for the MVP; production should use migrations.
- There is no PATCH endpoint yet.
- Customer IDs are case-normalized to uppercase.
- ARR is stored with `Numeric(14, 2)` and serialized as a string to avoid floating-point loss.
- Past renewal dates are allowed because overdue or historical customers may exist.
- The root `core-api` currently calls a legacy `/customers` path; CRM Part 2 implements the Version 4 `/crm/api/v1/customers` contract.

## PostgreSQL Migration Note

The session layer accepts any SQLAlchemy `DATABASE_URL`, and SQLite-specific options are isolated in `database/session.py`. The model uses SQLAlchemy types and constraints that can migrate to PostgreSQL with managed migrations in a production phase.
