<div align="center">

# OptiFlow AI

Dynamic enterprise simulation backend documentation is available in
[`docs/dynamic-enterprise-simulation.md`](docs/dynamic-enterprise-simulation.md).

### Autonomous Customer Escalation Portfolio Governor for B2B SaaS

A human-governed autonomous decision platform for allocating scarce enterprise specialists across competing customer escalations.

<br>

![React](https://img.shields.io/badge/Frontend-React%20%2B%20TypeScript-61DAFB?style=flat-square&logo=react&logoColor=black)
![FastAPI](https://img.shields.io/badge/Core-FastAPI-009688?style=flat-square&logo=fastapi&logoColor=white)
![LangGraph](https://img.shields.io/badge/Agent-LangGraph-1C3C3C?style=flat-square)
![Gemini](https://img.shields.io/badge/LLM-Gemini-8E75B2?style=flat-square&logo=google&logoColor=white)
![OR-Tools](https://img.shields.io/badge/Optimisation-OR--Tools%20CP--SAT-4285F4?style=flat-square&logo=google&logoColor=white)
![PostgreSQL](https://img.shields.io/badge/Database-PostgreSQL-4169E1?style=flat-square&logo=postgresql&logoColor=white)
![Docker](https://img.shields.io/badge/Deployment-Docker%20Compose-2496ED?style=flat-square&logo=docker&logoColor=white)

<br>

[Overview](#overview) •
[Features](#key-features) •
[Architecture](#system-architecture) •
[Repository](#repository-structure) •
[Setup](#getting-started) •
[Team](#team)

</div>

---

## Overview

OptiFlow AI is a human-governed autonomous decision platform designed for B2B SaaS customer operations.

When several high-impact customer escalations occur at the same time, managers must decide how to allocate a limited number of senior specialists.

OptiFlow evaluates the complete active escalation portfolio and recommends where each specialist should be assigned while considering:

- SLA deadlines
- Customer and commercial impact
- Renewal, launch and deal risks
- Required technical skills
- System-access permissions
- Specialist availability
- Capacity and workload
- Operational fatigue
- Customer fairness
- Business policies
- Human approval requirements

> **Core proposition:** Place each scarce specialist where the entire active customer portfolio benefits most, while preserving hard constraints, exposing trade-offs and keeping humans in control of high-impact actions.

---

## Problem

Traditional ticket-routing systems generally make decisions for one ticket at a time.

They usually answer:

> Who is available to handle this ticket?

OptiFlow instead answers:

> Which allocation across the entire active escalation portfolio minimises total SLA, commercial, customer, fairness and workforce harm?

A poor allocation can:

- Cause an avoidable SLA breach
- Delay an important customer launch
- Increase renewal or deal risk
- Overload a critical specialist
- Create unnecessary context switching
- Repeatedly postpone smaller customers
- Produce inconsistent and unauditable decisions

OptiFlow addresses this as a portfolio-level decision problem rather than a simple ticket-priority problem.

---

## Key Features

| Capability | Description |
|---|---|
| Goal interpretation | Converts a manager's natural-language objective into structured goals, constraints and preferences |
| Dynamic tool selection | Selects or skips enterprise services based on evidence needs and freshness |
| Evidence validation | Validates schemas, freshness, completeness, conflicts and provenance |
| Portfolio state building | Creates an immutable, versioned snapshot of customers, escalations and specialists |
| Consequence estimation | Estimates SLA, commercial, workload, fairness and delay consequences |
| CP-SAT optimisation | Generates feasible specialist allocation plans under explicit constraints |
| Plan comparison | Compares Current, SLA-First, Commercial-First and Balanced strategies |
| Deterministic validation | Enforces skills, access, availability, capacity, fairness and policy rules |
| Human approval | Requires authorised review before high-impact enterprise actions |
| Safe execution | Executes approved writes using version checks, verification and idempotency |
| Failure recovery | Handles retries, fallback evidence, partial execution and safe-pause states |
| Event-driven replanning | Replans when escalations, availability, SLA state or constraints change |
| Decision trace | Records evidence, alternatives, approvals, execution and outcomes |

---

# System Architecture

## Overall System Architecture

The following diagram shows the complete OptiFlow platform, including the React workspace, FastAPI core, LangGraph agent, deterministic engines, enterprise services and data ownership boundaries.

<p align="center">
  <img
    src="docs/images/architecture-overview.png"
    alt="OptiFlow AI overall system architecture"
    width="100%"
  >
</p>

### Main architectural rules

- The React frontend communicates with the FastAPI core using REST and Server-Sent Events.
- LangGraph coordinates the autonomous workflow inside the FastAPI core.
- Gemini interprets goals and explains validated outputs.
- Deterministic engines control calculations, feasibility, validation and execution safety.
- CRM, Incident, Workforce and Communication services are independent enterprise tools.
- Each enterprise tool owns a separate SQLite database.
- PostgreSQL stores OptiFlow decision, approval, checkpoint and audit data.
- The core accesses operational records only through enterprise service APIs.

---

## Autonomous Agent Lifecycle

The agent does not execute one fixed workflow for every request. Its route changes according to ambiguity, evidence quality, tool failures, plan feasibility, human decisions and operational events.

<p align="center">
  <img
    src="docs/images/agent-lifecycle.png"
    alt="OptiFlow AI conditional autonomous agent lifecycle"
    width="100%"
  >
</p>

The main lifecycle is:

```text
Business Goal
    ↓
Interpret Goal
    ↓
Clarify if Required
    ↓
Plan Evidence
    ↓
Select Enterprise Tools
    ↓
Gather and Validate Evidence
    ↓
Build Portfolio State
    ↓
Estimate Consequences
    ↓
Generate and Validate Plans
    ↓
Human Review
    ↓
Execute and Verify
    ↓
Monitor and Replan
```

---

## Detailed Architecture Diagrams

To keep the main README readable, the detailed diagrams are placed inside expandable sections.

<details>
<summary><strong>Engine Interaction and Decision Authority</strong></summary>

<br>

This diagram shows which component performs each operation and where decision authority belongs.

<p align="center">
  <img
    src="docs/images/engine-interaction.png"
    alt="OptiFlow AI engine interaction and authority"
    width="100%"
  >
</p>

### Authority model

- Gemini interprets and explains.
- Pydantic validates generated structures.
- Deterministic engines own calculations and decision enforcement.
- CP-SAT owns solver feasibility.
- Policy validators own pass, warning and fail results.
- Humans approve high-impact actions.
- The Execution Manager performs only authorised actions.

</details>

<details>
<summary><strong>End-to-End Data Flow</strong></summary>

<br>

This diagram shows how a natural-language manager goal is transformed into a verified enterprise execution.

<p align="center">
  <img
    src="docs/images/end-to-end-data-flow.png"
    alt="OptiFlow AI end-to-end data flow"
    width="100%"
  >
</p>

### Main data transformations

```text
Manager Goal
    ↓
Structured Goal
    ↓
Evidence Requirements
    ↓
Validated Tool Responses
    ↓
Canonical Portfolio State
    ↓
Consequence Matrix
    ↓
Candidate Plans
    ↓
Decision Package
    ↓
Approved Execution
    ↓
Execution Receipts and Events
```

Each stage preserves:

- Run ID
- Evidence IDs
- Source timestamps
- State version
- Plan version
- Policy version
- Approval ID
- Execution ID
- Idempotency keys
- Audit events

</details>

<details>
<summary><strong>CP-SAT, Validation and Human Approval</strong></summary>

<br>

This diagram shows how the canonical portfolio state is converted into four plans and validated before human approval.

<p align="center">
  <img
    src="docs/images/optimisation-human-approval.png"
    alt="OptiFlow AI CP-SAT validation and human approval"
    width="100%"
  >
</p>

### Compared strategies

1. Current Assignments
2. SLA-First
3. Commercial-First
4. OptiFlow Balanced

### Validation areas

- Skills and qualifications
- Access permissions
- Availability
- Capacity and workload
- Working-hour rules
- Customer fairness
- Fatigue and wellbeing
- Protected emergency capacity
- Evidence freshness
- Business policies

A plan that violates a hard constraint is marked infeasible and cannot be recommended.

</details>

<details>
<summary><strong>Execution, Failure Recovery and Replanning</strong></summary>

<br>

This diagram shows the approved execution saga, partial failure handling and event-driven replanning.

<p align="center">
  <img
    src="docs/images/execution-failure-recovery.png"
    alt="OptiFlow AI execution failure recovery and replanning"
    width="100%"
  >
</p>

### Safe execution sequence

1. Revalidate the approved state and plan.
2. Create a tentative workforce reservation.
3. Send a specialist assignment request.
4. Process the specialist response.
5. Assign the incident.
6. Confirm the workforce reservation.
7. Send notifications.
8. Verify authoritative enterprise state.
9. Store execution receipts.
10. Start monitoring.

If an operation fails, the system may retry, compensate, mark the execution as partial, pause safely or generate a new plan.

</details>

---

# Technology Stack

| Layer | Technology | Responsibility |
|---|---|---|
| Frontend | React, TypeScript and Tailwind CSS | Manager decision workspace |
| Core API | FastAPI | Public API, run management and execution authorisation |
| Agent orchestration | LangGraph | Conditional routing, checkpointing, pause/resume and replanning |
| Language model | Gemini through an internal adapter | Goal interpretation, clarification and explanation |
| Schema validation | Pydantic | Validation of LLM and service responses |
| Optimisation | Google OR-Tools CP-SAT | Constrained assignment and scheduling |
| Core database | PostgreSQL | Runs, states, plans, approvals, receipts and audit records |
| Tool databases | SQLite | Service-owned operational records |
| Commands and data | REST APIs | Frontend-to-core and core-to-tool communication |
| Live progress | Server-Sent Events | Real-time agent status updates |
| Deployment | Docker Compose | Reproducible local environment |
| Backend tests | Pytest | Unit and integration tests |
| Frontend tests | Vitest | Component and frontend logic tests |
| End-to-end tests | Playwright | Complete user and execution flow tests |

---

# Enterprise Services

## CRM Service

The CRM Service owns customer and commercial information.

Typical data includes:

- Customer identity
- Synthetic annual recurring revenue
- Customer tier
- Renewal date
- Account owner
- Strategic-account status
- Relationship context
- Commercial dependencies

Default port:

```text
8101
```

---

## Incident Service

The Incident Service owns escalation and SLA information.

Typical data includes:

- Escalation identity
- Customer reference
- Severity and priority
- SLA deadline
- Required skills
- Required access permissions
- Workaround status
- Current specialist assignment
- Incident status
- Assignment history

Default port:

```text
8102
```

---

## Workforce Service

The Workforce Service owns specialist and capacity information.

Typical data includes:

- Specialist profiles
- Skills and proficiency
- Access permissions
- Working hours
- Availability
- Current assignments
- Capacity and workload
- Operational fatigue indicators
- Protected emergency capacity
- Tentative reservations
- Confirmed reservations

Default port:

```text
8103
```

---

## Communication Service

The Communication Service owns assignment requests and notifications.

Typical data includes:

- Assignment requests
- Specialist acceptance or rejection
- Response reasons
- Internal notifications
- Delivery status
- Configured demonstration responses

Default port:

```text
8104
```

---

# Data Ownership

```text
CRM Service
└── Customer and commercial operational data
    └── CRM SQLite

Incident Service
└── Escalation, SLA and assignment operational data
    └── Incident SQLite

Workforce Service
└── Specialist, capacity, availability and reservation data
    └── Workforce SQLite

Communication Service
└── Assignment request, response and notification data
    └── Communication SQLite

OptiFlow Core
└── Decision and audit data
    └── PostgreSQL
```

The FastAPI core must not directly read tool-owned SQLite databases.

All operational information is accessed through the corresponding REST APIs.

---

# Repository Structure

```text
optiflow-ai/
│
├── frontend/
│   ├── public/
│   ├── src/
│   │   ├── api/
│   │   ├── components/
│   │   ├── events/
│   │   ├── features/
│   │   ├── pages/
│   │   ├── state/
│   │   ├── types/
│   │   ├── App.tsx
│   │   └── main.tsx
│   ├── package.json
│   ├── tsconfig.json
│   ├── vite.config.ts
│   └── Dockerfile
│
├── core-api/
│   ├── app/
│   │   ├── agent/
│   │   │   ├── nodes/
│   │   │   ├── edges/
│   │   │   ├── graph.py
│   │   │   └── state.py
│   │   │
│   │   ├── api/
│   │   │   ├── routes/
│   │   │   ├── dependencies.py
│   │   │   └── router.py
│   │   │
│   │   ├── approval/
│   │   ├── config/
│   │   ├── consequences/
│   │   ├── events/
│   │   ├── evidence/
│   │   ├── execution/
│   │   ├── goals/
│   │   ├── llm/
│   │   ├── models/
│   │   ├── monitoring/
│   │   ├── optimisation/
│   │   ├── persistence/
│   │   ├── policies/
│   │   ├── state_builder/
│   │   ├── tools/
│   │   └── main.py
│   │
│   ├── tests/
│   │   ├── unit/
│   │   ├── integration/
│   │   └── end_to_end/
│   │
│   ├── requirements.txt
│   └── Dockerfile
│
├── tools/
│   ├── crm-service/
│   │   ├── app/
│   │   │   ├── api/
│   │   │   ├── database/
│   │   │   ├── middleware/
│   │   │   ├── schemas/
│   │   │   ├── services/
│   │   │   └── main.py
│   │   ├── data/
│   │   ├── tests/
│   │   ├── requirements.txt
│   │   └── Dockerfile
│   │
│   ├── incident-service/
│   │   ├── app/
│   │   ├── data/
│   │   ├── tests/
│   │   ├── requirements.txt
│   │   └── Dockerfile
│   │
│   ├── workforce-service/
│   │   ├── app/
│   │   ├── data/
│   │   ├── tests/
│   │   ├── requirements.txt
│   │   └── Dockerfile
│   │
│   └── communication-service/
│       ├── app/
│       ├── data/
│       ├── tests/
│       ├── requirements.txt
│       └── Dockerfile
│
├── shared/
│   ├── python/
│   │   └── optiflow_shared/
│   ├── typescript/
│   ├── policies/
│   └── scenario-data/
│
├── database/
│   ├── migrations/
│   ├── seed/
│   └── init.sql
│
├── scenarios/
│   ├── demo.json
│   ├── edge-cases/
│   └── expected-results/
│
├── scripts/
│   ├── health-check.ps1
│   ├── health-check.sh
│   ├── reset-demo.ps1
│   ├── reset-demo.sh
│   ├── run-tests.ps1
│   └── run-tests.sh
│
├── docs/
│   ├── images/
│   │   ├── architecture-overview.png
│   │   ├── agent-lifecycle.png
│   │   ├── engine-interaction.png
│   │   ├── end-to-end-data-flow.png
│   │   ├── optimisation-human-approval.png
│   │   └── execution-failure-recovery.png
│   │
│   ├── architecture/
│   ├── implementation/
│   ├── api/
│   ├── demo/
│   └── testing/
│
├── docker-compose.yml
├── .env.example
├── .gitignore
├── README.md
└── LICENSE
```

## Directory responsibilities

| Directory | Purpose |
|---|---|
| `frontend/` | React decision workspace |
| `core-api/` | FastAPI, LangGraph, LLM adapter and deterministic engines |
| `tools/` | Independent CRM, Incident, Workforce and Communication services |
| `shared/` | Shared schemas, enums, policies and contracts |
| `database/` | PostgreSQL schema, migrations and seed data |
| `scenarios/` | Controlled demonstrations and edge cases |
| `scripts/` | Health, reset, demo and testing scripts |
| `docs/` | Architecture, API, implementation and visual documentation |

---

# Getting Started

For the competition walkthrough and the one-command fresh-laptop setup, use
[`docs/container-demo-setup.md`](docs/container-demo-setup.md).

## Prerequisites

Install:

- Git
- Docker Desktop
- Docker Compose v2

Docker Compose runs PostgreSQL, the four enterprise services, Core, and the
Nginx-served React frontend. Python and Node.js are not required on the demo laptop.

---

## 1. Clone the repository

```bash
git clone <repository-url>
cd optiflow-ai
```

Replace `<repository-url>` with the actual GitHub repository URL.

---

## 2. Create the environment file

### Windows PowerShell

```powershell
Copy-Item .env.example .env
```

### Linux or macOS

```bash
cp .env.example .env
```

Update the required configuration inside `.env`.

Do not commit the actual `.env` file.

---

## Configuration Management

The project uses one root `.env` file as the local source of configuration.

- `.env.example` is committed and contains placeholders or safe development defaults.
- `.env` is local only and is ignored by Git.
- `docker-compose.yml` reads values with `${VARIABLE_NAME}` references.
- Do not commit API keys, tokens, database passwords or generated local databases.
- When a required variable is added, add it to `.env.example`, read it through the application settings layer, and reference it from Compose where the container needs it.

---

## 3. Start the complete seeded application

### Windows PowerShell

```powershell
powershell -ExecutionPolicy Bypass -File .\scripts\start-demo.ps1 -Fresh -Force
```

### Linux / macOS

```bash
chmod +x scripts/start-demo.sh scripts/reset-demo.sh
./scripts/start-demo.sh --fresh --force
```

---

## 4. Open the application

| Service | Address |
|---|---|
| React frontend | `http://localhost:3000` |
| FastAPI core | `http://localhost:8000` |
| Core API documentation | `http://localhost:8000/docs` |
| CRM Service | `http://localhost:8101` |
| Incident Service | `http://localhost:8102` |
| Workforce Service | `http://localhost:8103` |
| Communication Service | `http://localhost:8104` |
| PostgreSQL | `localhost:5432` |

---

## 5. Check container status

### Windows PowerShell

```powershell
docker compose --profile full-stack ps
```

### Linux / Git Bash

```bash
docker compose --profile full-stack ps
```

---

## 6. Health check

### Windows PowerShell

```powershell
.\scripts\health-check.ps1
```

### Linux / Git Bash

```bash
./scripts/health-check.sh
```

The health scripts check PostgreSQL, Core API, CRM, Incident, Workforce and Communication services. They return exit code `0` only when required backend components are healthy.

---

## 7. Reset demo data

Normal deterministic reset:

```powershell
.\scripts\reset-demo.ps1
```

```bash
./scripts/reset-demo.sh
```

Destructive local reset with volume recreation:

```powershell
.\scripts\reset-demo.ps1 -RecreateVolumes
```

```bash
./scripts/reset-demo.sh --recreate-volumes
```

The destructive path asks for confirmation unless `-Force` or `--force` is supplied. Use it only for local demo data.

---

## 8. Run backend tests

### Windows PowerShell

```powershell
.\scripts\run-tests.ps1 -Mode all
.\scripts\run-tests.ps1 -Mode unit
.\scripts\run-tests.ps1 -Mode integration
```

### Linux / Git Bash

```bash
./scripts/run-tests.sh --mode all
./scripts/run-tests.sh --mode unit
./scripts/run-tests.sh --mode integration
```

The scripts continue through all selected suites, print a summary, and return non-zero if any required suite fails.

---

## 9. View logs

All services:

```bash
docker compose --profile full-stack logs -f
```

Core API only:

```bash
docker compose --profile full-stack logs -f core-api
```

CRM Service only:

```bash
docker compose --profile full-stack logs -f crm-service
```

---

## 10. Stop the system

### Windows PowerShell

```powershell
docker compose --profile full-stack down
```

Stop the local frontend with `Ctrl+C` in its Vite terminal.

### Linux / Git Bash

```bash
docker compose --profile full-stack down
```

Remove containers and generated volumes:

```bash
docker compose --profile full-stack down -v
```

Use `-v` only when all stored local database data should be removed.

---

## 11. Troubleshooting

- If `docker compose --profile full-stack ps` shows no services, start with `docker compose --profile full-stack up --build -d`.
- If ports are busy, change the host-side `*_PORT` values in `.env`; scripts derive host URLs from those values.
- If health checks fail, run `docker compose --profile full-stack logs -f core-api` and inspect the failing service logs.
- If tests fail because dependencies are missing, create the service virtual environments and install each `requirements.txt`.
- If Docker reports credential or Compose plugin errors, fix Docker Desktop or Docker CLI first, then rerun the command.
- Never fix local demo issues by committing `.env` or secrets.

---

# Local Development Without Docker

Each Python service should use a separate virtual environment.

## CRM Service

```powershell
cd tools\crm-service

python -m venv .venv
.\.venv\Scripts\Activate.ps1

pip install -r requirements.txt

uvicorn app.main:app --reload --port 8101
```

## Incident Service

```powershell
cd tools\incident-service

python -m venv .venv
.\.venv\Scripts\Activate.ps1

pip install -r requirements.txt

uvicorn app.main:app --reload --port 8102
```

## Workforce Service

```powershell
cd tools\workforce-service

python -m venv .venv
.\.venv\Scripts\Activate.ps1

pip install -r requirements.txt

uvicorn app.main:app --reload --port 8103
```

## Communication Service

```powershell
cd tools\communication-service

python -m venv .venv
.\.venv\Scripts\Activate.ps1

pip install -r requirements.txt

uvicorn app.main:app --reload --port 8104
```

## Core API

```powershell
cd core-api

python -m venv .venv
.\.venv\Scripts\Activate.ps1

pip install -r requirements.txt

uvicorn app.main:app --reload --port 8000
```

## Frontend

```powershell
cd frontend

npm install
npm run dev
```

---

# Environment Configuration

Use `.env.example` as the committed template. The local `.env` should contain the same variable names with developer-specific values.

Core examples:

```env
# Application
APP_ENV=development
APP_VERSION=4.0
SCENARIO_ID=phase2-demo

# Frontend
FRONTEND_PORT=3000
FRONTEND_CONTAINER_PORT=3000
VITE_CORE_API_URL=http://localhost:8000

# Core API
CORE_API_PORT=8000
CORE_API_CONTAINER_PORT=8000
CORE_API_HOST=0.0.0.0
CORE_LOG_LEVEL=INFO

# PostgreSQL
POSTGRES_HOST=postgres
POSTGRES_PORT=5432
POSTGRES_CONTAINER_PORT=5432
POSTGRES_DB=optiflow
POSTGRES_USER=optiflow
POSTGRES_PASSWORD=change-me
DATABASE_URL=postgresql+psycopg://optiflow:change-me@postgres:5432/optiflow

# Enterprise Services
CRM_SERVICE_URL=http://crm-service:8101
INCIDENT_SERVICE_URL=http://incident-service:8102
WORKFORCE_SERVICE_URL=http://workforce-service:8103
COMMUNICATION_SERVICE_URL=http://communication-service:8104

CRM_SERVICE_PORT=8101
CRM_SERVICE_CONTAINER_PORT=8101
INCIDENT_SERVICE_PORT=8102
INCIDENT_SERVICE_CONTAINER_PORT=8102
WORKFORCE_SERVICE_PORT=8103
WORKFORCE_SERVICE_CONTAINER_PORT=8103
COMMUNICATION_SERVICE_PORT=8104
COMMUNICATION_SERVICE_CONTAINER_PORT=8104

# Internal Service Authentication
TOOL_SHARED_TOKEN=change-me
ADMIN_API_KEY=change-me-admin

# Gemini
GEMINI_API_KEY=
GEMINI_MODEL=<PINNED_MODEL_ID>
GEMINI_TIMEOUT_SECONDS=8
GEMINI_MAX_RETRIES=1

# Agent
MAX_GRAPH_STEPS=40
MAX_CLARIFICATION_ROUNDS=1
MAX_REPLAN_COUNT=5

# Tool Execution
TOOL_TIMEOUT_SECONDS=3
MAX_TOOL_RETRIES=2
TOOL_RETRY_INITIAL_DELAY_MS=500

# Server-Sent Events
SSE_HEARTBEAT_SECONDS=15
SSE_QUEUE_SIZE=200

# Demonstration
DEMO_MODE=true
DEMO_DELAY_MS=300
DEMO_PORTFOLIO_TIMEOUT_SECONDS=3
DEMO_HEALTH_TIMEOUT_SECONDS=2
DEMO_ALLOW_FAILURE_INJECTION=true

# SAGA specialist response polling
SAGA_POLL_MAX_ATTEMPTS=5
SAGA_POLL_INTERVAL_SECONDS=1.0
```

Core demo APIs:

| Method | Path | Purpose |
|---|---|---|
| `GET` | `/api/v1/demo/portfolio` | Aggregate CRM, Incident, Workforce, workload, and Communication source data for the demo dashboard |
| `GET` | `/api/v1/demo/health` | Return Core, PostgreSQL, and enterprise-service readiness |
| `POST` | `/api/v1/demo/simulation/specialist-response` | Queue an accepted or rejected specialist response without exposing service admin credentials |
| `POST` | `/api/v1/demo/simulation/failure` | Enable or disable demo source failure simulation |
| `POST` | `/api/v1/demo/simulation/reset` | Reset deterministic demo service state |
| `GET` | `/api/v1/demo/simulation/state` | Read current demo simulation state |

Never commit:

- `.env`
- API keys
- Database passwords
- Shared service tokens
- Access credentials
- Private customer data

---

# Demonstration Scenario

The controlled demonstration uses four enterprise customers and three specialists.

## Customer escalations

| Customer | Escalation | Synthetic ARR | Critical context |
|---|---|---:|---|
| Alpha Bank | Payment API intermittently failing | 600,000 | SLA risk in approximately two hours; workaround exists |
| Nova Retail | Enterprise onboarding blocked | 1,200,000 | Production launch scheduled for tomorrow |
| GreenLogistics | Reporting defect | 180,000 | Renewal in five days; postponed twice |
| MediCore | Security questionnaire blocking deal | 400,000 | Deal decision expected this week |

## Specialists

| Specialist | Main capabilities | Constraint |
|---|---|---|
| Maya | Payments and API integration | Fatigued after recent overnight incidents |
| Daniel | Data pipelines and reporting | Does not have payment-system access |
| Nimal | Solution architecture and onboarding | Available for only two hours |

## Demonstrated behaviour

- Natural-language goal interpretation
- Clarification handling
- Dynamic enterprise service selection
- Evidence retrieval and validation
- Versioned portfolio state construction
- Consequence estimation
- Four-plan generation
- CP-SAT optimisation
- Policy, fairness and workload validation
- Human approval and modification
- Specialist assignment execution
- Specialist rejection handling
- Tool-failure recovery
- Event-driven replanning
- Complete Decision Trace updates

---

# Testing

## Backend tests

Use the Part 4 backend test scripts from the repository root.

### Windows PowerShell

```powershell
.\scripts\run-tests.ps1 -Mode all
```

### Linux / Git Bash

```bash
./scripts/run-tests.sh --mode all
```

Supported modes:

- `unit`: CRM, Incident, Workforce, Communication and Core unit tests.
- `integration`: repository integration tests.
- `all`: unit and integration tests.

The scripts report missing required test folders instead of silently skipping them.

## Frontend tests

```bash
npm test
```

## End-to-end tests

```bash
npx playwright test
```

## Recommended coverage

- Health endpoints
- Authentication and authorisation
- Request and response validation
- Tool-service isolation
- SQLite persistence
- PostgreSQL persistence
- Idempotent writes
- Dynamic tool selection
- Evidence freshness
- Conflicting evidence
- Clarification routes
- CP-SAT feasibility
- CP-SAT infeasibility
- Fairness constraints
- Workload constraints
- Approval enforcement
- Approval invalidation
- Assignment rejection
- Partial execution recovery
- Replanning limits
- SSE event ordering
- Scenario reset
- Complete end-to-end execution

---

# Safety and Governance

OptiFlow follows these principles:

- Unknown values remain unknown.
- Missing enterprise values are never invented.
- Every external response must pass schema validation.
- Hard constraints are enforced deterministically.
- The language model cannot approve actions.
- The language model cannot override solver output.
- The language model cannot waive policies.
- High-impact actions require backend-enforced approval.
- Approval is bound to the exact state, plan and policy versions.
- Approval is invalidated after a material state change.
- Enterprise writes use idempotency keys.
- Tool-owned databases cannot be accessed directly by the core.
- Protected personal characteristics are not used in allocation scoring.
- Secrets and credentials are excluded from audit events.
- Unrestricted model chain-of-thought is not stored or exposed.
- Partial execution is never displayed as complete success.
- Tool failures result in retry, fallback, compensation or safe pause.
- Every material decision remains versioned and auditable.

---

# Team

## We3 Prompters

| Member | Contribution |
|---|---|
| N. Ananthasagaran | Development, architecture and integration |
| U. Arnikan | Development, services and integration |
| U. Sanjeevan | Development, agent core and integration |

---

# Contributing

Create a feature branch:

```bash
git checkout -b feature/your-feature-name
```

Add your changes:

```bash
git add .
```

Commit your changes:

```bash
git commit -m "Add feature description"
```

Push the branch:

```bash
git push origin feature/your-feature-name
```

Open a pull request and request a review before merging into the main branch.

---

# Licence

This project is developed by the We3 Prompters team.

Add the selected licence to the root `LICENSE` file before public distribution.
