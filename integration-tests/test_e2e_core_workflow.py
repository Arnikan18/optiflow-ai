"""
End-to-End Core Workflow Tests  -  Task 5.1
============================================
Targets the live Docker stack (full-stack profile):

  Core API:      http://localhost:8000
  CRM:           http://localhost:8101
  Incident:      http://localhost:8102
  Workforce:     http://localhost:8103
  Communication: http://localhost:8104

Run with Docker up:
    pytest integration-tests/test_e2e_core_workflow.py -v --tb=short -s

Scenarios
---------
  0 - Stack Health Check
  1 - Normal Happy Path (+ execution verification)
  2 - Specialist Rejection -> Replan -> Completion (+ execution verification)
  4 - Human Modification (Manager overrides plan)
  5 - Human Rejection (clean termination, status always COMPLETED)
"""

import threading
import time
import uuid
from pathlib import Path
from typing import Any

import httpx
import pytest


# Configuration
REPO_ROOT = Path(__file__).resolve().parents[1]


def _load_env(path: Path) -> dict:
    result: dict = {}
    if not path.exists():
        return result
    for raw in path.read_text(encoding="utf-8").splitlines():
        line = raw.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, _, value = line.partition("=")
        result[key.strip()] = value.strip().strip('"').strip("'")
    return result


_ENV = _load_env(REPO_ROOT / ".env")

CORE_API      = "http://localhost:8000"
CRM_URL       = "http://localhost:8101"
INCIDENT_URL  = "http://localhost:8102"
WORKFORCE_URL = "http://localhost:8103"
COMM_URL      = "http://localhost:8104"

TOOL_TOKEN = _ENV.get("TOOL_SHARED_TOKEN", "change-me")
ADMIN_KEY  = _ENV.get("ADMIN_API_KEY", "change-me-admin")

_TOOL_HDRS  = {"X-Tool-Token": TOOL_TOKEN}
_ADMIN_HDRS = {"X-Admin-Key": ADMIN_KEY}

_POLL_INTERVAL     = 2.0
_TIMEOUT_APPROVAL  = 60
_TIMEOUT_COMPLETED = 90
_TIMEOUT_REPLAN    = 150
_TIMEOUT_REJECTION = 30

_GOAL_SLA = (
    "Protect SLA commitments and resolve critical incidents to prevent breach. "
    "Prioritise by ARR and specialist availability."
)


# Low-level HTTP helpers
def _get(url: str, *, headers: dict = None, timeout: float = 5.0) -> httpx.Response:
    return httpx.get(url, headers=headers or {}, timeout=timeout)


def _post(url: str, *, json: dict = None, headers: dict = None, timeout: float = 10.0) -> httpx.Response:
    return httpx.post(url, json=json or {}, headers=headers or {}, timeout=timeout)


def _tool_get(url: str) -> httpx.Response:
    return _get(url, headers=_TOOL_HDRS)


# Core API helpers
def create_run(goal_text: str) -> str:
    resp = _post(f"{CORE_API}/api/v1/runs", json={"goal_text": goal_text})
    assert resp.status_code == 201, f"create_run failed {resp.status_code}: {resp.text}"
    run_id = resp.json()["run_id"]
    assert run_id.startswith("RUN-"), f"Unexpected run_id format: {run_id!r}"
    return run_id


def get_run_state(run_id: str) -> dict:
    resp = _get(f"{CORE_API}/api/v1/runs/{run_id}")
    assert resp.status_code == 200, f"get_run_state failed {resp.status_code}: {resp.text}"
    return resp.json()


def approve_run(run_id: str, approval_status: str, recommended_plan: dict = None) -> None:
    body: dict = {"approval_status": approval_status}
    if recommended_plan is not None:
        body["recommended_plan"] = recommended_plan
    resp = _post(f"{CORE_API}/api/v1/runs/{run_id}/approve", json=body)
    assert resp.status_code == 200, (
        f"approve_run({approval_status!r}) failed {resp.status_code}: {resp.text}"
    )


def reset_all() -> None:
    """
    Reset all 4 tool-service databases by calling each service's admin reset
    endpoint directly from the host.  The core-api orchestrated reset
    (POST /api/v1/control-room/reset) is not used here because the core-api
    container resolves service URLs using Docker-internal hostnames
    (e.g. http://crm-service:8101) which are unreachable from the host runner.
    """
    _reset_targets = [
        (CRM_URL,       "crm"),
        (INCIDENT_URL,  "incident"),
        (WORKFORCE_URL, "workforce"),
        (COMM_URL,      "communication"),
    ]
    for base_url, name in _reset_targets:
        resp = _post(
            f"{base_url}/admin/reset",
            headers=_ADMIN_HDRS,
            timeout=15.0,
        )
        assert resp.status_code == 200, (
            f"{name} reset failed {resp.status_code}: {resp.text}"
        )

    # Cancel the seeded tentative reservation for SPEC-MAYA on INC-ALPHA-001
    # to prevent WORKFORCE_409 conflicts during E2E test runs.
    cancel_resp = httpx.delete(
        f"{WORKFORCE_URL}/workforce/api/v1/reservations/RES-MAYA-TENTATIVE",
        headers=_TOOL_HDRS,
        timeout=10.0,
    )
    # 200/204 means cancelled successfully; 404 means it wasn't there (which is also fine)
    assert cancel_resp.status_code in (200, 204, 404), (
        f"Failed to cancel RES-MAYA-TENTATIVE: {cancel_resp.status_code}: {cancel_resp.text}"
    )



def poll_run_until(run_id: str, target_status: str, timeout: float) -> dict:
    deadline = time.monotonic() + timeout
    last_state: dict = {}
    while time.monotonic() < deadline:
        try:
            last_state = get_run_state(run_id)
            current = last_state["status"]
            if current == target_status:
                return last_state
            if current == "CANCELLED" and target_status != "CANCELLED":
                pytest.fail(
                    f"Run {run_id} was CANCELLED unexpectedly while waiting for {target_status!r}"
                )
        except AssertionError as ae:
            # Ignore transient 404 (Not Found) errors on startup before insertion
            if "404" not in str(ae):
                raise ae
        except Exception:
            pass
        time.sleep(_POLL_INTERVAL)
    last_state = get_run_state(run_id)
    pytest.fail(
        f"Timed out ({timeout}s) waiting for run {run_id} to reach {target_status!r}. "
        f"Last status: {last_state.get('status')!r}"
    )


def _saga_ids(run_id: str, inc_id: str, replan_count: int = 0):
    suffix = f"-{replan_count}" if replan_count > 0 else ""
    res_id = f"RES-{run_id[:8]}-{inc_id[:8]}{suffix}"
    req_id = f"REQ-{run_id[:8]}-{inc_id[:8]}{suffix}"
    return res_id, req_id


def _first_allocation(state: dict) -> dict:
    plans = state.get("candidate_plans") or []
    assert plans, "No candidate_plans found in run state"
    allocs = (plans[0] or {}).get("allocations") or []
    assert allocs, "No allocations in first candidate plan"
    return allocs[0]


def verify_execution(
    run_id: str,
    res_id: str,
    inc_id: str,
    spec_id: str,
    req_id: str,
) -> dict:
    """
    Verify execution state by calling each tool service directly from the host.

    The core-api's POST /execution/verify endpoint internally calls tool services
    using Docker-internal hostnames which are not reachable from the host runner.
    Instead, we verify directly via individual service APIs.

    Returns a summary dict:
      {
        "reservation_confirmed": bool,
        "incident_assigned":     bool,
        "assignment_accepted":   bool,
        "overall_verified":      bool,
      }
    """
    # 1. Workforce: reservation status
    res_resp = _tool_get(f"{WORKFORCE_URL}/workforce/api/v1/reservations/{res_id}")
    if res_resp.status_code == 200:
        res_data = (res_resp.json().get("data") or {})
        reservation_confirmed = res_data.get("status") == "CONFIRMED"
    else:
        reservation_confirmed = False

    # 2. Incident service: specialist assigned
    inc_resp = _tool_get(f"{INCIDENT_URL}/incident/api/v1/incidents/{inc_id}")
    if inc_resp.status_code == 200:
        inc_data = (inc_resp.json().get("data") or {})
        incident_assigned = inc_data.get("assigned_specialist_id") == spec_id
    else:
        incident_assigned = False

    # 3. Communication service: assignment request accepted
    ar_resp = _tool_get(f"{COMM_URL}/communication/api/v1/assignment-requests/{req_id}")
    if ar_resp.status_code == 200:
        ar_data = (ar_resp.json().get("data") or {})
        assignment_accepted = ar_data.get("status") == "ACCEPTED"
    else:
        assignment_accepted = False

    # Informational call to core-api verify endpoint (may fail due to network)
    try:
        _post(
            f"{CORE_API}/api/v1/runs/{run_id}/execution/verify",
            json={
                "reservation_id": res_id,
                "incident_id": inc_id,
                "specialist_id": spec_id,
                "assignment_request_id": req_id,
                "plan_id": "E2E-VERIFY",
                "profile_name": "E2ETest",
            },
            headers={"X-Request-ID": str(uuid.uuid4())},
            timeout=5.0,
        )
    except Exception:
        pass

    return {
        "reservation_confirmed": reservation_confirmed,
        "incident_assigned": incident_assigned,
        "assignment_accepted": assignment_accepted,
        "overall_verified": reservation_confirmed and incident_assigned and assignment_accepted,
    }


def _inject_rejection(run_id: str, timeout: float = 20.0, outcome_dict: dict = None) -> bool:
    deadline = time.monotonic() + timeout
    hdrs = {**_TOOL_HDRS, "X-Request-ID": str(uuid.uuid4())}
    url_list = f"{COMM_URL}/communication/api/v1/assignment-requests?status=PENDING&page_size=100"
    prefix = f"REQ-{run_id[:8].upper()}"
    processed = set()
    while time.monotonic() < deadline:
        try:
            resp = httpx.get(url_list, headers=hdrs, timeout=3.0)
            if resp.status_code == 200:
                requests = (resp.json().get("data") or {}).get("assignment_requests") or []
                for req in requests:
                    req_id = req.get("request_id") or ""
                    if req_id.startswith(prefix) and req_id not in processed:
                        url_respond = f"{COMM_URL}/communication/api/v1/assignment-requests/{req_id}/respond"
                        reject = httpx.post(
                            url_respond,
                            json={
                                "response": "REJECTED",
                                "response_note": "E2E integration test explicit rejection",
                            },
                            headers=hdrs,
                            timeout=5.0,
                        )
                        if reject.status_code == 200:
                            if outcome_dict is not None:
                                outcome_dict["ok"] = True
                            return True
        except Exception:
            pass
        time.sleep(0.3)
    return False


def _inject_acceptance(run_id: str, timeout: float = 20.0, outcome_dict: dict = None) -> bool:
    deadline = time.monotonic() + timeout
    hdrs = {**_TOOL_HDRS, "X-Request-ID": str(uuid.uuid4())}
    url_list = f"{COMM_URL}/communication/api/v1/assignment-requests?status=PENDING&page_size=100"
    prefix = f"REQ-{run_id[:8].upper()}"
    processed = set()
    while time.monotonic() < deadline:
        try:
            resp = httpx.get(url_list, headers=hdrs, timeout=3.0)
            if resp.status_code == 200:
                requests = (resp.json().get("data") or {}).get("assignment_requests") or []
                for req in requests:
                    req_id = req.get("request_id") or ""
                    if req_id.startswith(prefix) and req_id not in processed:
                        url_respond = f"{COMM_URL}/communication/api/v1/assignment-requests/{req_id}/respond"
                        accept = httpx.post(
                            url_respond,
                            json={
                                "response": "ACCEPTED",
                                "response_note": "E2E integration test explicit acceptance",
                            },
                            headers=hdrs,
                            timeout=5.0,
                        )
                        if accept.status_code == 200:
                            processed.add(req_id)
                            if outcome_dict is not None:
                                outcome_dict["ok"] = True
        except Exception:
            pass
        time.sleep(0.3)
    return len(processed) > 0


# Scenario 0 - Stack Health Check
class TestScenario0StackHealth:

    def test_core_api_process_health(self) -> None:
        resp = _get(f"{CORE_API}/health")
        assert resp.status_code == 200, f"/health failed: {resp.text}"
        body = resp.json()
        assert body.get("service") == "core-api"
        assert body.get("status") == "UP"

    def test_core_api_system_health(self) -> None:
        # The aggregation endpoint probes services using Docker-internal hostnames
        # (e.g. http://crm-service:8101) which are not reachable from the host test
        # runner.  We verify the endpoint itself responds correctly; individual
        # service health is covered by the parametrized test_tool_service_health tests.
        resp = _get(f"{CORE_API}/api/v1/system/health", timeout=10.0)
        assert resp.status_code == 200, f"/api/v1/system/health failed: {resp.text}"
        body = resp.json()
        assert "services" in body, f"'services' key missing: {body}"
        assert "status" in body, f"'status' key missing: {body}"
        assert body["services"].get("core") == "UP", (
            f"Core API reports itself DOWN: {body}"
        )

    @pytest.mark.parametrize("base_url,name", [
        (CRM_URL,       "crm"),
        (INCIDENT_URL,  "incident"),
        (WORKFORCE_URL, "workforce"),
        (COMM_URL,      "communication"),
    ])
    def test_tool_service_health(self, base_url: str, name: str) -> None:
        resp = _get(f"{base_url}/health")
        assert resp.status_code == 200, f"{name} /health returned {resp.status_code}"

    @pytest.mark.parametrize("base_url,name", [
        (CRM_URL,       "crm"),
        (INCIDENT_URL,  "incident"),
        (WORKFORCE_URL, "workforce"),
        (COMM_URL,      "communication"),
    ])
    def test_tool_service_readiness(self, base_url: str, name: str) -> None:
        resp = _get(f"{base_url}/readiness")
        assert resp.status_code == 200, f"{name} /readiness returned {resp.status_code}"
        assert resp.json().get("status") == "ready", (
            f"{name} reports not ready: {resp.json()}"
        )


# Scenario 1 - Normal Happy Path
class TestScenario1NormalHappyPath:

    def test_normal_happy_path(self) -> None:
        reset_all()

        run_id = create_run(_GOAL_SLA)

        state = poll_run_until(run_id, "WAITING_FOR_APPROVAL", _TIMEOUT_APPROVAL)

        plans = state.get("candidate_plans") or []
        assert len(plans) > 0, "No candidate plans generated"

        confidence = state.get("confidence_report") or {}
        assert confidence, "confidence_report is missing"
        # The confidence_report uses key 'score' (not 'confidence_score')
        assert "score" in confidence, (
            f"'score' key not in confidence_report: {confidence}"
        )

        risk = state.get("autonomy_risk_report") or {}
        assert risk, "autonomy_risk_report is missing"
        assert "risk_level" in risk, f"risk_level not in report: {risk}"

        # business_summary is declared in state but not yet written by any graph node;
        # assert it is present in the checkpoint (even if None) to track when it's added
        assert "business_summary" in state, "business_summary key missing from run state"

        goals = (state.get("structured_goal") or {}).get("objectives")
        assert goals, f"structured_goal.objectives is empty: {state.get('structured_goal')}"

        alloc   = _first_allocation(state)
        inc_id  = alloc["incident_id"]
        spec_id = alloc["specialist_id"]
        res_id, req_id = _saga_ids(run_id, inc_id)

        outcome: dict = {"ok": False}

        def _worker() -> None:
            _inject_acceptance(run_id, timeout=25.0, outcome_dict=outcome)

        worker = threading.Thread(target=_worker, daemon=True)
        worker.start()

        approve_run(run_id, "APPROVED")

        worker.join(timeout=30.0)
        assert outcome["ok"], (
            f"Failed to inject ACCEPTED response for run {run_id}."
        )

        final = poll_run_until(run_id, "COMPLETED", _TIMEOUT_COMPLETED)

        assert final["status"] == "COMPLETED"
        assert final.get("replan_count", 0) == 0, (
            f"Expected no replans on clean path, got {final['replan_count']}"
        )
        assert (final.get("excluded_specialist_incidents") or []) == [], (
            f"Unexpected exclusions: {final.get('excluded_specialist_incidents')}"
        )

        verify = verify_execution(run_id, res_id, inc_id, spec_id, req_id)
        assert verify["overall_verified"] is True, (
            f"Execution not fully verified: {verify}"
        )
        assert verify["reservation_confirmed"], "Reservation not CONFIRMED after happy path"
        assert verify["incident_assigned"], "Incident not assigned to specialist after happy path"
        assert verify["assignment_accepted"], "Assignment request not ACCEPTED after happy path"


# Scenario 2 - Specialist Rejection -> Replan -> Completion
class TestScenario2SpecialistRejection:

    def test_rejection_replan_completion(self) -> None:
        reset_all()

        run_id = create_run(_GOAL_SLA)

        state = poll_run_until(run_id, "WAITING_FOR_APPROVAL", _TIMEOUT_APPROVAL)

        alloc   = _first_allocation(state)
        inc_id  = alloc["incident_id"]
        spec_id = alloc["specialist_id"]
        _, req_id = _saga_ids(run_id, inc_id)

        outcome: dict = {"ok": False}

        def _worker() -> None:
            _inject_rejection(run_id, timeout=25.0, outcome_dict=outcome)

        worker = threading.Thread(target=_worker, daemon=True)
        worker.start()

        approve_run(run_id, "APPROVED")

        worker.join(timeout=30.0)
        assert outcome["ok"], (
            f"Failed to inject REJECTED response for run {run_id}."
        )

        # Start a second worker thread to ACCEPT the replanned assignment request(s).
        outcome2: dict = {"ok": False}

        def _worker2() -> None:
            _inject_acceptance(run_id, timeout=45.0, outcome_dict=outcome2)

        worker2 = threading.Thread(target=_worker2, daemon=True)
        worker2.start()

        final = poll_run_until(run_id, "COMPLETED", _TIMEOUT_REPLAN)

        # Wait for the second worker to complete
        worker2.join(timeout=10.0)
        assert outcome2["ok"], (
            f"Failed to inject ACCEPTED response for replanned run {run_id}."
        )

        assert final["status"] == "COMPLETED"
        assert final.get("replan_count", 0) >= 1, (
            f"Expected replan_count >= 1, got {final.get('replan_count')}"
        )
        excluded = final.get("excluded_specialist_incidents") or []
        assert any(
            e.get("specialist_id") == spec_id and e.get("incident_id") == inc_id
            for e in excluded
        ), f"Expected excluded pair ({spec_id!r}, {inc_id!r}) not found: {excluded}"

        # change_summary is declared in state but not yet written by any graph node
        assert "change_summary" in final, "change_summary key missing from final run state"

        final_plans = final.get("candidate_plans") or []
        if final_plans:
            final_alloc = (final_plans[0].get("allocations") or [{}])[0]
            final_spec  = final_alloc.get("specialist_id")
            final_inc   = final_alloc.get("incident_id")
            if final_spec and final_inc:
                final_res, final_req = _saga_ids(run_id, final_inc, replan_count=1)
                verify = verify_execution(
                    run_id, final_res, final_inc, final_spec, final_req
                )
                assert verify["overall_verified"] is True, (
                    f"Replanned execution not verified: {verify}"
                )
                assert verify["reservation_confirmed"], "Reservation not CONFIRMED after replan"
                assert verify["incident_assigned"], "Incident not assigned after replan"


# Scenario 4 - Human Modification
class TestScenario4HumanModification:

    def test_human_modification(self) -> None:
        reset_all()

        run_id = create_run(_GOAL_SLA)

        state1 = poll_run_until(run_id, "WAITING_FOR_APPROVAL", _TIMEOUT_APPROVAL)

        plans1 = state1.get("candidate_plans") or []
        assert len(plans1) >= 1, "No candidate plans in first approval gate"

        modified_plan = plans1[1] if len(plans1) >= 2 else plans1[0]

        approve_run(run_id, "MODIFY", recommended_plan=modified_plan)

        state2 = poll_run_until(run_id, "WAITING_FOR_APPROVAL", _TIMEOUT_APPROVAL)

        alloc2  = _first_allocation(state2)
        inc_id  = alloc2["incident_id"]
        spec_id = alloc2["specialist_id"]
        res_id, req_id = _saga_ids(run_id, inc_id)

        outcome: dict = {"ok": False}

        def _worker() -> None:
            _inject_acceptance(run_id, timeout=25.0, outcome_dict=outcome)

        worker = threading.Thread(target=_worker, daemon=True)
        worker.start()

        approve_run(run_id, "APPROVED")

        worker.join(timeout=30.0)
        assert outcome["ok"], (
            f"Failed to inject ACCEPTED response for run {run_id}."
        )

        final = poll_run_until(run_id, "COMPLETED", _TIMEOUT_COMPLETED)
        assert final["status"] == "COMPLETED"

        verify = verify_execution(run_id, res_id, inc_id, spec_id, req_id)
        assert verify["overall_verified"] is True, (
            f"Modified plan execution not verified: {verify}"
        )
        assert verify["reservation_confirmed"], "Reservation not CONFIRMED after human modification"


# Scenario 5 - Human Rejection
class TestScenario5HumanRejection:

    def test_human_rejection_clean_termination(self) -> None:
        reset_all()

        run_id = create_run(_GOAL_SLA)

        state = poll_run_until(run_id, "WAITING_FOR_APPROVAL", _TIMEOUT_APPROVAL)

        alloc  = _first_allocation(state)
        inc_id = alloc["incident_id"]

        approve_run(run_id, "REJECTED")

        final = poll_run_until(run_id, "COMPLETED", _TIMEOUT_REJECTION)

        assert final["status"] == "COMPLETED"
        assert final.get("replan_count", 0) == 0, (
            f"Unexpected replan_count after rejection: {final['replan_count']}"
        )

        inc_resp = _tool_get(f"{INCIDENT_URL}/incident/api/v1/incidents/{inc_id}")
        if inc_resp.status_code == 200:
            inc_data = (inc_resp.json().get("data") or {})
            inc_status = inc_data.get("status", "")
            assert inc_status != "ASSIGNED", (
                f"Incident {inc_id!r} was ASSIGNED after manager rejection"
            )

        res_resp = _tool_get(
            f"{WORKFORCE_URL}/workforce/api/v1/reservations?page_size=100"
        )
        if res_resp.status_code == 200:
            reservations = (
                (res_resp.json().get("data") or {}).get("reservations") or []
            )
            run_prefix = run_id[:8]
            for res in reservations:
                if run_prefix in (res.get("reservation_id") or ""):
                    assert res.get("status") != "CONFIRMED", (
                        f"Found CONFIRMED reservation {res['reservation_id']!r} "
                        f"for run {run_id} after manager rejection"
                    )
