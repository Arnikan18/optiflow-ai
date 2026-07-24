# OptiFlow AI - Core API & AI Core Architecture Guide (Version 4.0)

This document is the official developer reference for **Member 1 (AI Core & Agent Optimisation)** under the Version 4 Aligned Technical Proposal.

---

## 1. AI Core Architecture Overview

The AI Core coordinates natural-language input interpretation, evidence planning, data gathering, constraint solving, write validation, and SAGA execution.

```
                  +-----------------------------------+
                  |      Vite + React Frontend        |
                  +-----------------------------------+
                                    │
                               REST / SSE
                                    ▼
                  +-----------------------------------+
                  |        FastAPI Core API           |
                  |     (app/main.py: App Route)      |
                  +-----------------------------------+
                                    │
                              ainvoke(state)
                                    ▼
                  +-----------------------------------+
                  |      LangGraph Orchestrator       |
                  |     (app/agent/graph.py)          |
                  +-----------------------------------+
                     /              |              \
                    /               |               \
                   v                v                v
            [Interpreter]      [Planner]       [ToolClient]
             Gemini / fallback  EvidenceRegistry   HTTP Adapter
```

---

## 2. Core API Endpoints

The Core API has been updated to support Version 4 routes prefixed with `/api/v1` while retaining deprecated endpoints to support older UI interactions:

*   **System Status**:
    - `GET /api/v1/system/health`: Aggregates health status of core engine, postgres, and tool microservices concurrently.
    - `GET /api/system/health` (deprecated legacy mapping)
*   **Demo Control & Portfolio**:
    - `GET /api/v1/demo/portfolio`: Queries tool databases concurrently via adapters and returns the aggregated customer, incident, specialist, and request lists.
    - `GET /api/demo/portfolio` (deprecated legacy mapping)
    - `POST /api/v1/control-room/reset`: Authenticates admin keys and resets mock databases.
    - `POST /api/control/reset` (deprecated legacy mapping)
*   **Run Control**:
    - `POST /api/v1/runs`: Submits a goal to start the LangGraph workflow.
    - `GET /api/v1/runs/{run_id}`: Retrieves run status.

---

## 3. LangGraph Workflow & Execution Flow

The workflow models a conditional state machine that supports loops, pauses, and approvals.

### **Node Sequence & Transition Rules**
1.  **`receive_goal`**: Registers run ID.
2.  **`interpret_goal`**: Parses user intent via Gemini (falling back to rule-based parser on outages).
3.  **`validate_goal`**: Evaluates policy constraints.
    - *Conditional Route*:
        - `NEEDS_CLARIFICATION` -> Routes to `pause_for_clarification` -> halts at `END`.
        - `FAILED_SAFE` -> Routes to `complete_run` -> halts at `END`.
        - `PLANNING` -> Routes to `plan_evidence`.
4.  **`plan_evidence`**: Translates StructuredGoal to EvidenceRequirements list.
5.  **`select_tools`**: Evaluates registry service ownership mapping.
6.  **`execute_tools`**: Resolves endpoints and queries service databases.
7.  **`build_state`**: Compiles portfolio into normalized `EnterpriseState`.
8.  **`evaluate_quality`**: Validates evidence freshness, missing fields, and conflicts.
9.  **`generate_plans`**: Runs CP-SAT optimization profiles.
10. **`pause_for_approval`**: Waits for manager review.
    - *Conditional Route*:
        - `APPROVED` -> Routes to `execute_saga`.
        - `MODIFY` -> Routes back to `interpret_goal` (Clarification/Re-planning Loop).
        - `REJECTED` -> Routes to `complete_run`.
        - `PENDING` -> Halts execution at `END` waiting for validation resume points.
11. **`execute_saga`**: Writes tentative records and verifies outcomes.
12. **`complete_run`**: Registers run conclusion.

---

## 4. AgentState Schema

The `AgentState` maps the Minimum LangGraph Run State:

| Field Name | Type | Purpose |
| :--- | :--- | :--- |
| `run_id` | `str` | Unique autonomous lifecycle identifier |
| `status` | `str` | Current execution status |
| `current_node` | `str` | Current LangGraph node |
| `goal_text` | `str` | Original manager input text |
| `structured_goal` | `dict` | Parsed objectives and horizons |
| `required_evidence`| `list` | Evidence requirements derived by the planner |
| `collected_evidence`| `list`| Fetched operational records |
| `source_freshness` | `dict` | Freshness status of tool databases |
| `data_conflicts` | `list` | Unresolved contradictory values |
| `consequence_estimates` | `list` | Cost exposure variables |
| `candidate_plans` | `list` | Alternative schedule choices |
| `recommended_plan` | `dict` | Target plan recommendation |
| `approval_status` | `str` | Manager control state |
| `execution_receipts`| `list`| Receipts confirming SAGA outcomes |

---

## 5. ToolClient Adapter Architecture

To prevent scattered HTTP calls, all Core-to-Tool service communication is centralized inside `ToolClient` (`core-api/app/adapters/tool_client.py`).

*   **Security & Tracing**: Injects authentication headers (`X-Tool-Token`) and propagates correlation tracking identifiers (`X-Request-ID`).
*   **Envelope Extraction**: Decouples services by extracting target `data` from the JSON envelopes before returning payloads to core reasoning steps.
*   **Outage Defense**: Handles network failures, timeouts, and translates HTTP error ranges to standard system error logs.
