# Member 3 Backend Integration Contract

This contract documents frontend-safe Core API endpoints. The frontend must call the Core API only; it must not call internal Docker service admin endpoints or store backend secrets.

## Security Rules

- Do not send `ADMIN_API_KEY` to the browser.
- Do not store `TOOL_SHARED_TOKEN` in frontend code, browser storage or environment variables exposed by Vite.
- Do not call `crm-service`, `incident-service`, `workforce-service` or `communication-service` Docker hostnames from the browser.
- Use `VITE_CORE_API_URL` for the public Core API base URL.
- Send `X-Request-ID` when practical so backend logs and responses can be correlated.

Core demo endpoints currently use no frontend authentication in the MVP. Demo write controls are gated server-side by `DEMO_MODE` and `DEMO_ALLOW_FAILURE_INJECTION`.

## Response Wrapper

Core demo responses use:

```json
{
  "success": true,
  "message": "Request completed successfully",
  "timestamp": "2026-07-29T00:00:00Z",
  "data": {}
}
```

Error responses may use FastAPI `detail` for Core validation/permission errors. The frontend should display a concise message and keep the last known good state when possible.

## Endpoints

### Portfolio

`GET /api/v1/demo/portfolio`

Purpose: dashboard-ready portfolio state aggregated from CRM, Incident, Workforce, workload and Communication sources.

Authentication: none in MVP.

Headers:

- Optional `X-Request-ID`

Response data:

- `generated_at`
- `degraded`
- `customers`
- `incidents`
- `specialists`
- `workloads`
- `portfolio_summary`
- `sources`

Polling safety: safe to refresh. Recommended refresh frequency is 10-30 seconds, or manual refresh during demos.

Frontend states:

- Loading: keep layout stable while the request is pending.
- Empty: show empty tables/metrics when arrays are empty.
- Degraded: if `degraded=true`, show available sections and source-level warnings; do not fabricate missing source data.

### Demo Health

`GET /api/v1/demo/health`

Purpose: Core, PostgreSQL and enterprise-service readiness.

Response data:

- `overall_status`: `HEALTHY`, `DEGRADED`, or `UNHEALTHY`
- `checked_at`
- `components[]`: `name`, `status`, `latency_ms`, `checked_at`, optional `message`

Recommended refresh frequency: 5-15 seconds on a health/status surface.

### Simulation State

`GET /api/v1/demo/simulation/state`

Purpose: read temporary demo state, communication queued responses and active failure modes.

Response data:

- `communication`
- `services`
- `degraded`
- `generated_at`

Polling safety: safe to refresh. Recommended refresh frequency is 5-10 seconds while a demo control drawer is open.

Disabled state: if `DEMO_MODE=false`, Core returns `403`.

### Queue Specialist Response

`POST /api/v1/demo/simulation/specialist-response`

Purpose: ask Core to queue a deterministic Communication response without exposing admin credentials.

Request body:

```json
{
  "specialist_id": "SPEC-MAYA",
  "incident_id": "INC-ALPHA-001",
  "status": "ACCEPTED",
  "reason": "Available for this escalation",
  "response_delay_seconds": 0,
  "apply_once": true,
  "expires_after_seconds": 900
}
```

Rules:

- `status` must be `ACCEPTED` or `REJECTED`.
- Specialist + incident match has highest priority.
- Specialist-only matching is next.
- Generic fallback is supported only when no specialist/incident are supplied intentionally.
- `apply_once=true` consumes the rule after one use.

Frontend handling: disable submit while pending, then refresh simulation state.

### Configure Failure Simulation

`POST /api/v1/demo/simulation/failure`

Purpose: enable or disable source failure simulation through Core.

Request body:

```json
{
  "service": "crm",
  "enabled": true,
  "failure_type": "HTTP_ERROR",
  "status_code": 503,
  "delay_seconds": 0,
  "affected_endpoint": "crm:list",
  "scope": "crm",
  "apply_once": false,
  "expires_after_seconds": 900,
  "message": "CRM unavailable for demo"
}
```

Supported services: `crm`, `incident`, `workforce`, `communication`.

Supported failure types: `HTTP_ERROR`, `TIMEOUT`, `DELAY`, `CONNECTION_FAILURE`, `INVALID_RESPONSE`.

Disabled state: if `DEMO_MODE=false` or `DEMO_ALLOW_FAILURE_INJECTION=false`, Core returns `403`.

### Reset Simulation / Demo Data

`POST /api/v1/demo/simulation/reset`

Purpose: reset deterministic demo service state through Core.

Request body:

```json
{
  "services": ["crm", "incident", "workforce", "communication"]
}
```

`services` may be omitted to reset all supported demo services.

Frontend handling: show a confirmation before calling, then refresh portfolio, health and simulation state.

### Execution Verification

`POST /api/v1/runs/{run_id}/execution/verify`

Purpose: display authoritative verification of a completed execution attempt.

Request body:

```json
{
  "reservation_id": "RES-RUN-001-INC-ALPHA-001-SPEC-MAYA",
  "incident_id": "INC-ALPHA-001",
  "specialist_id": "SPEC-MAYA",
  "assignment_request_id": "AR-RUN-001-INC-ALPHA-001-SPEC-MAYA",
  "plan_id": "PLAN-BALANCED",
  "profile_name": "Balanced"
}
```

Response data:

- `run_id`
- `overall_verified`
- `workforce_verification`
- `incident_verification`
- `communication_verification`
- `failed_components`
- `checked_at`
- `recommended_next_state`
- `execution_receipt`

Frontend handling:

- `overall_verified=true`: show verified/completed state.
- `recommended_next_state=WAITING`: show pending/source recovery state.
- `REPLAN` or `COMPENSATE`: show recovery path and avoid success wording.
- `FAILED`: show safe-pause/operator review state.

### Portfolio Profiles / Plans

There is no standalone public profile endpoint in the current backend. Portfolio profiles are exposed through run state:

- `POST /api/v1/runs` starts a run.
- `GET /api/v1/runs/{run_id}` returns `candidate_plans` when planning has produced them.
- `GET /api/v1/runs/{run_id}/stream` streams run events through SSE.

Each CP-SAT plan includes profile metadata such as `profile_id`, `profile_name`, `description`, `assignments`, `objective_weights`, `objective_value`, `solver_status`, `feasible`, `generated_at`, `solve_time_ms`, and comparable metrics.

## TypeScript Interfaces

```ts
export interface ApiEnvelope<T> {
  success: boolean;
  message: string;
  timestamp: string;
  data: T;
}

export interface SourceStatus {
  source_name: string;
  status: "AVAILABLE" | "UNAVAILABLE" | "TIMEOUT" | "INVALID_RESPONSE" | "AUTH_FAILED";
  freshness_timestamp: string | null;
  response_time_ms: number | null;
  error_code?: string | null;
  error_message?: string | null;
}

export interface PortfolioSummary {
  total_customers: number | null;
  total_active_incidents: number | null;
  total_at_risk_customers: number | null;
  total_arr_represented: number | null;
  total_arr_at_risk: number | null;
  total_specialists: number | null;
  available_specialists: number | null;
  average_workload: number | null;
  incidents_near_sla_breach: number | null;
  unassigned_incidents: number | null;
  generated_at: string;
  partial: boolean;
}

export interface DemoPortfolio {
  generated_at: string;
  degraded: boolean;
  customers: Array<Record<string, unknown>>;
  incidents: Array<Record<string, unknown>>;
  specialists: Array<Record<string, unknown>>;
  workloads: Array<Record<string, unknown>>;
  portfolio_summary: PortfolioSummary;
  sources: SourceStatus[];
}

export interface HealthComponent {
  name: string;
  status: "HEALTHY" | "DEGRADED" | "UNHEALTHY";
  latency_ms: number | null;
  checked_at: string;
  message?: string | null;
}

export interface DemoHealth {
  overall_status: "HEALTHY" | "DEGRADED" | "UNHEALTHY";
  checked_at: string;
  components: HealthComponent[];
}

export interface ExecutionVerification {
  run_id: string;
  overall_verified: boolean;
  failed_components: string[];
  checked_at: string;
  recommended_next_state: "COMPLETED" | "WAITING" | "COMPENSATE" | "REPLAN" | "FAILED";
  workforce_verification: Record<string, unknown>;
  incident_verification: Record<string, unknown>;
  communication_verification: Record<string, unknown>;
  execution_receipt: Record<string, unknown>;
}
```

## Refresh Guidance

- Portfolio: 10-30 seconds, or manual refresh after demo actions.
- Health: 5-15 seconds while the system status panel is visible.
- Simulation state: 5-10 seconds while demo controls are open.
- Run status: 2-5 seconds if SSE is unavailable.
- SSE stream: prefer `GET /api/v1/runs/{run_id}/stream` for live run updates.
