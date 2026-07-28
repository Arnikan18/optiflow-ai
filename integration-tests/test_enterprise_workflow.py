import os
import socket
import subprocess
import sys
import time
import uuid
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import httpx
import pytest


REPO_ROOT = Path(__file__).resolve().parents[1]
SHARED_ROOT = REPO_ROOT / "shared" / "python"
TOOL_TOKEN = "integration-tool-token"
ADMIN_KEY = "integration-admin-key"
REQUEST_ID_HEADER = "X-Request-ID"


@dataclass(frozen=True)
class ServiceDef:
    name: str
    root: Path
    database_name: str


SERVICE_DEFS = {
    "crm": ServiceDef("crm-service", REPO_ROOT / "tools" / "crm-service", "crm.db"),
    "incident": ServiceDef("incident-service", REPO_ROOT / "tools" / "incident-service", "incident.db"),
    "workforce": ServiceDef("workforce-service", REPO_ROOT / "tools" / "workforce-service", "workforce.db"),
    "communication": ServiceDef(
        "communication-service",
        REPO_ROOT / "tools" / "communication-service",
        "communication.db",
    ),
}


def _free_port() -> int:
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as sock:
        sock.bind(("127.0.0.1", 0))
        return int(sock.getsockname()[1])


def _wait_for_readiness(base_url: str, process: subprocess.Popen[str]) -> None:
    deadline = time.monotonic() + 30
    last_error: Exception | None = None
    while time.monotonic() < deadline:
        if process.poll() is not None:
            output = process.stdout.read() if process.stdout else ""
            raise RuntimeError(f"service exited before readiness: {output}")
        try:
            response = httpx.get(f"{base_url}/readiness", timeout=2)
            if response.status_code == 200 and response.json().get("status") == "ready":
                return
        except Exception as exc:
            last_error = exc
        time.sleep(0.5)
    raise RuntimeError(f"service did not become ready at {base_url}: {last_error}")


def _start_service(service: ServiceDef, port: int, data_dir: Path) -> subprocess.Popen[str]:
    env = os.environ.copy()
    env.update(
        {
            "ADMIN_API_KEY": ADMIN_KEY,
            "ASSIGNMENT_REQUEST_TTL_SECONDS": "900",
            "DATABASE_URL": f"sqlite:///{(data_dir / service.database_name).as_posix()}",
            "ENABLE_SEED_DATA": "true",
            "LOG_LEVEL": "WARNING",
            "MAX_PAGE_SIZE": "100",
            "MAX_REQUEST_ID_LENGTH": "128",
            "REQUEST_ID_HEADER": REQUEST_ID_HEADER,
            "RESERVATION_TTL_SECONDS": "300",
            "SERVICE_NAME": service.name,
            "SERVICE_PORT": str(port),
            "SIMULATED_DELIVERY_MODE": "success",
            "TOOL_SHARED_TOKEN": TOOL_TOKEN,
        }
    )
    existing_pythonpath = env.get("PYTHONPATH")
    env["PYTHONPATH"] = os.pathsep.join(
        [str(SHARED_ROOT), str(service.root)] + ([existing_pythonpath] if existing_pythonpath else [])
    )

    return subprocess.Popen(
        [
            sys.executable,
            "-m",
            "uvicorn",
            "app.main:app",
            "--host",
            "127.0.0.1",
            "--port",
            str(port),
            "--log-level",
            "warning",
        ],
        cwd=service.root,
        env=env,
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        text=True,
    )


@dataclass(frozen=True)
class Stack:
    bases: dict[str, str]
    processes: list[subprocess.Popen[str]]


@pytest.fixture(scope="session")
def stack(tmp_path_factory) -> Stack:
    ports = {name: _free_port() for name in SERVICE_DEFS}
    data_dir = tmp_path_factory.mktemp("enterprise-service-dbs")
    processes: list[subprocess.Popen[str]] = []
    bases: dict[str, str] = {}

    try:
        for service_name, service in SERVICE_DEFS.items():
            process = _start_service(service, ports[service_name], data_dir)
            processes.append(process)
            bases[service_name] = f"http://127.0.0.1:{ports[service_name]}"

        for service_name, process in zip(SERVICE_DEFS, processes):
            _wait_for_readiness(bases[service_name], process)

        yield Stack(bases=bases, processes=processes)
    finally:
        for process in processes:
            if process.poll() is None:
                process.terminate()
        for process in processes:
            try:
                process.wait(timeout=10)
            except subprocess.TimeoutExpired:
                process.kill()
                process.wait(timeout=5)


class ServiceClient:
    def __init__(self, base_url: str) -> None:
        self.base_url = base_url

    def request(
        self,
        method: str,
        path: str,
        *,
        json: dict[str, Any] | None = None,
        request_id: str | None = None,
        admin: bool = False,
    ) -> httpx.Response:
        headers = {"X-Tool-Token": TOOL_TOKEN}
        if admin:
            headers["X-Admin-Key"] = ADMIN_KEY
        if request_id:
            headers[REQUEST_ID_HEADER] = request_id
        return httpx.request(method, f"{self.base_url}{path}", headers=headers, json=json, timeout=5)

    def get(self, path: str, *, request_id: str | None = None) -> httpx.Response:
        return self.request("GET", path, request_id=request_id)

    def post(
        self,
        path: str,
        *,
        json: dict[str, Any] | None = None,
        request_id: str | None = None,
        admin: bool = False,
    ) -> httpx.Response:
        return self.request("POST", path, json=json, request_id=request_id, admin=admin)

    def patch(self, path: str, *, json: dict[str, Any] | None = None, request_id: str | None = None) -> httpx.Response:
        return self.request("PATCH", path, json=json, request_id=request_id)


@pytest.fixture()
def clients(stack: Stack) -> dict[str, ServiceClient]:
    clients = {name: ServiceClient(base_url) for name, base_url in stack.bases.items()}
    for client in clients.values():
        response = client.post("/admin/reset", admin=True, request_id=str(uuid.uuid4()))
        assert response.status_code == 200, response.text
        assert response.json()["success"] is True
    return clients


def _data(response: httpx.Response, status_code: int = 200) -> dict[str, Any]:
    assert response.status_code == status_code, response.text
    body = response.json()
    assert body["success"] is True
    assert body["timestamp"].endswith("Z")
    return body["data"]


def _assert_error(response: httpx.Response, status_code: int, error_code: str, request_id: str) -> dict[str, Any]:
    assert response.status_code == status_code, response.text
    assert response.headers[REQUEST_ID_HEADER] == request_id
    body = response.json()
    assert body["success"] is False
    assert body["errorCode"] == error_code
    assert body["timestamp"].endswith("Z")
    assert "requestId" not in body
    return body


def test_enterprise_assignment_e2e_workflow(clients: dict[str, ServiceClient]) -> None:
    request_id = str(uuid.uuid4())
    crm = clients["crm"]
    incident = clients["incident"]
    workforce = clients["workforce"]
    communication = clients["communication"]

    customer = _data(crm.get("/crm/api/v1/customers/CUS-ALPHA", request_id=request_id))
    incident_id = "INC-P6-E2E-001"
    created_incident = _data(
        incident.post(
            "/incident/api/v1/incidents",
            request_id=request_id,
            json={
                "incident_id": incident_id,
                "customer_id": customer["customer_id"],
                "title": "Part 6 enterprise workflow incident",
                "description": "End-to-end workflow coverage for enterprise services.",
                "priority": "CRITICAL",
                "sla_deadline": "2099-07-24T15:00:00Z",
            },
        ),
        status_code=201,
    )
    assert created_incident["customer_id"] == customer["customer_id"]

    available = _data(
        workforce.get("/workforce/api/v1/specialists/available?skill=technical&required_capacity=1", request_id=request_id)
    )
    specialist = available["specialists"][0]
    specialist_id = specialist["specialist_id"]

    reservation_id = "RES-P6-E2E-001"
    reservation = _data(
        workforce.post(
            "/workforce/api/v1/reservations",
            request_id=request_id,
            json={
                "reservation_id": reservation_id,
                "specialist_id": specialist_id,
                "incident_id": incident_id,
                "expires_in_seconds": 300,
            },
        ),
        status_code=201,
    )
    assert reservation["status"] == "TENTATIVE"

    assigned_incident = _data(
        incident.post(
            f"/incident/api/v1/incidents/{incident_id}/assign",
            request_id=request_id,
            json={"specialist_id": specialist_id},
        )
    )
    assert assigned_incident["assigned_specialist_id"] == specialist_id

    assignment_id = "AR-P6-E2E-001"
    assignment = _data(
        communication.post(
            "/communication/api/v1/assignment-requests",
            request_id=request_id,
            json={
                "request_id": assignment_id,
                "incident_id": incident_id,
                "specialist_id": specialist_id,
                "message": "Please accept the Part 6 end-to-end assignment.",
                "expires_in_seconds": 900,
            },
        ),
        status_code=201,
    )
    assert assignment["status"] == "PENDING"

    accepted_assignment = _data(
        communication.post(
            f"/communication/api/v1/assignment-requests/{assignment_id}/respond",
            request_id=request_id,
            json={"response": "ACCEPTED", "response_note": "Accepted for Part 6 workflow."},
        )
    )
    assert accepted_assignment["status"] == "ACCEPTED"

    confirmed_reservation = _data(
        workforce.patch(f"/workforce/api/v1/reservations/{reservation_id}/confirm", request_id=request_id)
    )
    assert confirmed_reservation["status"] == "CONFIRMED"

    in_progress_incident = _data(
        incident.patch(
            f"/incident/api/v1/incidents/{incident_id}/status",
            request_id=request_id,
            json={"status": "IN_PROGRESS"},
        )
    )
    assert in_progress_incident["status"] == "IN_PROGRESS"

    notification_payload = {
        "notification_id": "NOT-P6-E2E-001",
        "recipient": specialist.get("email") or "ops@example.test",
        "channel": "EMAIL",
        "subject": "Part 6 assignment accepted",
        "message": "Assignment request AR-P6-E2E-001 was accepted.",
        "related_request_id": assignment_id,
        "idempotency_key": "idem-p6-e2e-001",
    }
    notification = _data(
        communication.post(
            "/communication/api/v1/notifications",
            request_id=request_id,
            json=notification_payload,
        ),
        status_code=201,
    )
    assert notification["status"] == "DELIVERED"

    replayed_notification = _data(
        communication.post(
            "/communication/api/v1/notifications",
            request_id=request_id,
            json=notification_payload,
        )
    )
    assert replayed_notification["notification_id"] == notification["notification_id"]

    assert _data(crm.get(f"/crm/api/v1/customers/{customer['customer_id']}", request_id=request_id))["customer_id"] == "CUS-ALPHA"
    assert _data(incident.get(f"/incident/api/v1/incidents/{incident_id}", request_id=request_id))["assigned_specialist_id"] == specialist_id
    assert _data(workforce.get(f"/workforce/api/v1/specialists/{specialist_id}", request_id=request_id))["specialist_id"] == specialist_id
    assert _data(workforce.get(f"/workforce/api/v1/reservations/{reservation_id}", request_id=request_id))["incident_id"] == incident_id
    assert _data(communication.get(f"/communication/api/v1/assignment-requests/{assignment_id}", request_id=request_id))["specialist_id"] == specialist_id
    assert _data(communication.get("/communication/api/v1/notifications/NOT-P6-E2E-001", request_id=request_id))["related_request_id"] == assignment_id


def test_request_id_is_preserved_on_successes_and_errors(clients: dict[str, ServiceClient]) -> None:
    request_id = str(uuid.uuid4())

    for client in clients.values():
        success = client.get("/health", request_id=request_id)
        assert success.status_code == 200
        assert success.headers[REQUEST_ID_HEADER] == request_id

    _assert_error(clients["crm"].get("/crm/api/v1/customers/CUS-MISSING", request_id=request_id), 404, "CRM_404", request_id)
    _assert_error(
        clients["incident"].get("/incident/api/v1/incidents/INC-MISSING", request_id=request_id),
        404,
        "INCIDENT_404",
        request_id,
    )
    _assert_error(
        clients["workforce"].get("/workforce/api/v1/specialists/SPEC-MISSING", request_id=request_id),
        404,
        "WORKFORCE_404",
        request_id,
    )
    _assert_error(
        clients["communication"].get("/communication/api/v1/assignment-requests/AR-MISSING", request_id=request_id),
        404,
        "COMMUNICATION_404",
        request_id,
    )


def test_negative_enterprise_contracts(clients: dict[str, ServiceClient]) -> None:
    request_id = str(uuid.uuid4())
    crm = clients["crm"]
    incident = clients["incident"]
    workforce = clients["workforce"]
    communication = clients["communication"]

    _assert_error(crm.get("/crm/api/v1/customers/CUS-MISSING", request_id=request_id), 404, "CRM_404", request_id)

    customer_payload = {
        "customer_id": "CUS-P6-DUP",
        "name": "Part 6 Duplicate Customer",
        "tier": "Enterprise",
        "arr": "100000.00",
        "renewal_date": "2099-01-01",
        "active": True,
    }
    _data(crm.post("/crm/api/v1/customers", json=customer_payload, request_id=request_id), status_code=201)
    _assert_error(
        crm.post("/crm/api/v1/customers", json=customer_payload, request_id=request_id),
        409,
        "CRM_409",
        request_id,
    )

    incident_payload = {
        "incident_id": "INC-P6-DUP",
        "customer_id": "CUS-ALPHA",
        "title": "Duplicate incident coverage",
        "description": "Part 6 negative duplicate incident test.",
        "priority": "HIGH",
        "sla_deadline": "2099-07-24T16:00:00Z",
    }
    _data(incident.post("/incident/api/v1/incidents", json=incident_payload, request_id=request_id), status_code=201)
    _assert_error(
        incident.post("/incident/api/v1/incidents", json=incident_payload, request_id=request_id),
        409,
        "INCIDENT_409",
        request_id,
    )
    _assert_error(
        incident.patch(
            "/incident/api/v1/incidents/INC-OMEGA-001/status",
            json={"status": "OPEN"},
            request_id=request_id,
        ),
        409,
        "INCIDENT_409",
        request_id,
    )

    _assert_error(
        workforce.get("/workforce/api/v1/specialists/SPEC-MISSING", request_id=request_id),
        404,
        "WORKFORCE_404",
        request_id,
    )
    _assert_error(
        workforce.post(
            "/workforce/api/v1/reservations",
            request_id=request_id,
            json={
                "reservation_id": "RES-P6-CAPACITY",
                "specialist_id": "SPEC-NIMAL",
                "incident_id": "INC-P6-CAPACITY",
            },
        ),
        409,
        "WORKFORCE_409",
        request_id,
    )
    _assert_error(
        workforce.post(
            "/workforce/api/v1/reservations",
            request_id=request_id,
            json={
                "reservation_id": "RES-P6-DUPACTIVE",
                "specialist_id": "SPEC-MAYA",
                "incident_id": "INC-ALPHA-001",
            },
        ),
        409,
        "WORKFORCE_409",
        request_id,
    )
    _assert_error(
        workforce.patch("/workforce/api/v1/reservations/RES-DANIEL-EXPIRED/confirm", request_id=request_id),
        409,
        "WORKFORCE_409",
        request_id,
    )

    _assert_error(
        communication.get("/communication/api/v1/assignment-requests/AR-MISSING", request_id=request_id),
        404,
        "COMMUNICATION_404",
        request_id,
    )
    _assert_error(
        communication.post(
            "/communication/api/v1/assignment-requests/AR-ACCEPTED-001/respond",
            request_id=request_id,
            json={"response": "REJECTED", "response_note": "Opposite final response."},
        ),
        409,
        "COMMUNICATION_409",
        request_id,
    )

    notification_payload = {
        "notification_id": "NOT-P6-IDEMPOTENT",
        "recipient": "maya.sen@example.test",
        "channel": "EMAIL",
        "subject": "Part 6 idempotency",
        "message": "Part 6 idempotency duplicate should return existing notification.",
        "idempotency_key": "idem-p6-negative",
    }
    notification = _data(
        communication.post(
            "/communication/api/v1/notifications",
            json=notification_payload,
            request_id=request_id,
        ),
        status_code=201,
    )
    replayed = _data(
        communication.post(
            "/communication/api/v1/notifications",
            json=notification_payload,
            request_id=request_id,
        )
    )
    assert replayed["notification_id"] == notification["notification_id"]
    conflict_payload = {**notification_payload, "notification_id": "NOT-P6-IDEMPOTENT-2", "message": "Different payload."}
    _assert_error(
        communication.post(
            "/communication/api/v1/notifications",
            json=conflict_payload,
            request_id=request_id,
        ),
        409,
        "COMMUNICATION_409",
        request_id,
    )

    invalid_admin_headers = {"X-Admin-Key": "wrong-key", REQUEST_ID_HEADER: request_id}
    for name, client in clients.items():
        response = httpx.post(f"{client.base_url}/admin/reset", headers=invalid_admin_headers, timeout=5)
        namespace = "COMMUNICATION" if name == "communication" else name.upper()
        _assert_error(response, 401, f"{namespace}_401", request_id)

    _assert_error(
        crm.post(
            "/crm/api/v1/customers",
            json={"customer_id": ""},
            request_id=request_id,
        ),
        422,
        "CRM_422",
        request_id,
    )
