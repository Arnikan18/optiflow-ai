from datetime import datetime, timezone


def assert_success(response, status_code=200):
    assert response.status_code == status_code
    body = response.json()
    assert body["success"] is True
    assert "timestamp" in body
    return body["data"]


def assert_error(response, status_code, error_code):
    assert response.status_code == status_code
    body = response.json()
    assert body["success"] is False
    assert body["errorCode"] == error_code
    assert "timestamp" in body
    return body


def incident_payload(**overrides):
    payload = {
        "incident_id": "inc-test-001",
        "customer_id": "cus-alpha",
        "title": "Checkout latency spike",
        "description": "Checkout latency exceeded normal operating thresholds.",
        "priority": "high",
        "sla_deadline": "2099-08-01T10:00:00Z",
        "estimated_effort_minutes": 90,
        "required_skills": [" Payments ", "API-Integration", "payments"],
    }
    payload.update(overrides)
    return payload


def test_health_readiness_and_docs(client):
    assert client.get("/health").json() == {"status": "healthy", "service": "incident-service"}

    readiness = client.get("/readiness")
    assert readiness.status_code == 200
    assert readiness.json()["database"] == "reachable"

    assert client.get("/docs").status_code == 200


def test_list_default_pagination_and_legacy_active_route(client, auth_headers):
    data = assert_success(client.get("/incident/api/v1/incidents", headers=auth_headers))
    assert data["page"] == 1
    assert data["page_size"] == 20
    assert data["total_items"] == 9
    assert data["total_pages"] == 1
    assert [item["incident_id"] for item in data["incidents"]][:2] == [
        "INC-OMEGA-001",
        "INC-ALPHA-001",
    ]

    page_two = assert_success(client.get("/incident/api/v1/incidents?page=2&page_size=3", headers=auth_headers))
    assert page_two["incidents"]
    beyond = assert_success(client.get("/incident/api/v1/incidents?page=99", headers=auth_headers))
    assert beyond["incidents"] == []

    legacy = client.get("/escalations/active", headers=auth_headers)
    assert legacy.status_code == 200
    assert {item["escalationId"] for item in legacy.json()} == {
        "INC-ALPHA-001",
        "INC-NOVA-001",
        "INC-GREEN-001",
        "INC-ORBIT-001",
        "INC-HARBOR-001",
        "INC-NOVA-002",
        "INC-SUMMIT-001",
    }


def test_list_filters_search_and_sla_ranges(client, auth_headers):
    critical = assert_success(client.get("/incident/api/v1/incidents?priority=critical", headers=auth_headers))
    assert [item["incident_id"] for item in critical["incidents"]] == [
        "INC-ALPHA-001",
        "INC-ORBIT-001",
    ]

    open_items = assert_success(client.get("/incident/api/v1/incidents?status=open", headers=auth_headers))
    assert {item["incident_id"] for item in open_items["incidents"]} == {
        "INC-ALPHA-001",
        "INC-GREEN-001",
        "INC-NOVA-002",
        "INC-ORBIT-001",
        "INC-SUMMIT-001",
    }

    customer = assert_success(client.get("/incident/api/v1/incidents?customer_id= cus-nova ", headers=auth_headers))
    assert [item["incident_id"] for item in customer["incidents"]] == [
        "INC-NOVA-002",
        "INC-NOVA-001",
    ]

    assigned = assert_success(client.get("/incident/api/v1/incidents?assigned_specialist_id=spec-nimal", headers=auth_headers))
    assert [item["incident_id"] for item in assigned["incidents"]] == ["INC-NOVA-001"]

    unassigned = assert_success(client.get("/incident/api/v1/incidents?unassigned=true", headers=auth_headers))
    assert {item["incident_id"] for item in unassigned["incidents"]} == {
        "INC-ALPHA-001",
        "INC-GREEN-001",
        "INC-NOVA-002",
        "INC-ORBIT-001",
        "INC-SUMMIT-001",
    }

    overdue = assert_success(client.get("/incident/api/v1/incidents?overdue=true", headers=auth_headers))
    assert [item["incident_id"] for item in overdue["incidents"]] == ["INC-ALPHA-001"]

    search = assert_success(client.get("/incident/api/v1/incidents?search=report", headers=auth_headers))
    assert [item["incident_id"] for item in search["incidents"]] == ["INC-GREEN-001"]

    window = assert_success(
        client.get(
            "/incident/api/v1/incidents?sla_after=2099-01-01T00:00:00Z&sla_before=2099-12-31T23:59:59Z",
            headers=auth_headers,
        )
    )
    assert {item["incident_id"] for item in window["incidents"]} == {"INC-NOVA-001", "INC-GREEN-001"}


def test_get_incident_existing_missing_assigned_unassigned_closed(client, auth_headers):
    existing = assert_success(client.get("/incident/api/v1/incidents/inc-nova-001", headers=auth_headers))
    assert existing["assigned_specialist_id"] == "SPEC-NIMAL"
    assert existing["status"] == "IN_PROGRESS"

    unassigned = assert_success(client.get("/incident/api/v1/incidents/INC-GREEN-001", headers=auth_headers))
    assert unassigned["assigned_specialist_id"] is None

    closed = assert_success(client.get("/incident/api/v1/incidents/INC-OMEGA-001", headers=auth_headers))
    assert closed["status"] == "CLOSED"

    assert_error(client.get("/incident/api/v1/incidents/INC-MISSING", headers=auth_headers), 404, "INCIDENT_404")


def test_create_incident_defaults_normalizes_and_rejects_duplicate(client, auth_headers):
    created = assert_success(
        client.post("/incident/api/v1/incidents", json=incident_payload(), headers=auth_headers),
        201,
    )
    assert created["incident_id"] == "INC-TEST-001"
    assert created["customer_id"] == "CUS-ALPHA"
    assert created["priority"] == "HIGH"
    assert created["status"] == "OPEN"
    assert created["estimated_effort_minutes"] == 90
    assert created["required_skills"] == ["payments", "api-integration"]
    assert created["assigned_specialist_id"] is None
    assert created["created_at"] <= created["updated_at"]

    duplicate = client.post("/incident/api/v1/incidents", json=incident_payload(), headers=auth_headers)
    assert_error(duplicate, 409, "INCIDENT_409")

    assigned = assert_success(
        client.post(
            "/incident/api/v1/incidents",
            json=incident_payload(
                incident_id="inc-test-002",
                assigned_specialist_id=" spec-maya ",
                priority="CRITICAL",
            ),
            headers=auth_headers,
        ),
        201,
    )
    assert assigned["assigned_specialist_id"] == "SPEC-MAYA"


def test_status_transition_matrix_and_idempotency(client, auth_headers):
    before = assert_success(client.get("/incident/api/v1/incidents/INC-GREEN-001", headers=auth_headers))

    in_progress = assert_success(
        client.patch(
            "/incident/api/v1/incidents/INC-GREEN-001/status",
            json={"status": "in progress"},
            headers=auth_headers,
        )
    )
    assert in_progress["status"] == "IN_PROGRESS"
    assert in_progress["updated_at"] >= before["updated_at"]

    retry = assert_success(
        client.patch(
            "/incident/api/v1/incidents/INC-GREEN-001/status",
            json={"status": "IN_PROGRESS"},
            headers=auth_headers,
        )
    )
    assert retry["updated_at"] == in_progress["updated_at"]

    resolved = assert_success(
        client.patch(
            "/incident/api/v1/incidents/INC-GREEN-001/status",
            json={"status": "RESOLVED"},
            headers=auth_headers,
        )
    )
    assert resolved["status"] == "RESOLVED"

    assert_error(
        client.patch(
            "/incident/api/v1/incidents/INC-GREEN-001/status",
            json={"status": "OPEN"},
            headers=auth_headers,
        ),
        409,
        "INCIDENT_409",
    )
    assert_error(
        client.patch(
            "/incident/api/v1/incidents/INC-OMEGA-001/status",
            json={"status": "OPEN"},
            headers=auth_headers,
        ),
        409,
        "INCIDENT_409",
    )


def test_assignment_rules(client, auth_headers):
    assigned = assert_success(
        client.post(
            "/incident/api/v1/incidents/INC-GREEN-001/assign",
            json={"specialist_id": "spec-daniel"},
            headers=auth_headers,
        )
    )
    assert assigned["assigned_specialist_id"] == "SPEC-DANIEL"

    same = assert_success(
        client.post(
            "/incident/api/v1/incidents/INC-GREEN-001/assign",
            json={"specialist_id": "SPEC-DANIEL"},
            headers=auth_headers,
        )
    )
    assert same["updated_at"] == assigned["updated_at"]

    reassigned = assert_success(
        client.post(
            "/incident/api/v1/incidents/INC-GREEN-001/assign",
            json={"specialist_id": "SPEC-MAYA"},
            headers=auth_headers,
        )
    )
    assert reassigned["assigned_specialist_id"] == "SPEC-MAYA"
    assert reassigned["status"] == "OPEN"

    assert_error(
        client.post(
            "/incident/api/v1/incidents/INC-MEDI-001/assign",
            json={"specialist_id": "SPEC-MAYA"},
            headers=auth_headers,
        ),
        409,
        "INCIDENT_409",
    )
    assert_error(
        client.post(
            "/incident/api/v1/incidents/INC-OMEGA-001/assign",
            json={"specialist_id": "SPEC-MAYA"},
            headers=auth_headers,
        ),
        409,
        "INCIDENT_409",
    )
    assert_error(
        client.post(
            "/incident/api/v1/incidents/INC-MISSING/assign",
            json={"specialist_id": "SPEC-MAYA"},
            headers=auth_headers,
        ),
        404,
        "INCIDENT_404",
    )


def assignment_verification_payload(**overrides):
    payload = {
        "incident_id": "INC-GREEN-001",
        "expected_run_id": "RUN-VERIFY-001",
        "expected_specialist_id": "SPEC-DANIEL",
    }
    payload.update(overrides)
    return payload


def test_verify_incident_assignment_correct_wrong_specialist_and_wrong_run(client, auth_headers):
    assigned = assert_success(
        client.post(
            "/incident/api/v1/incidents/INC-GREEN-001/assign",
            json={
                "specialist_id": "SPEC-DANIEL",
                "run_id": "RUN-VERIFY-001",
                "idempotency_key": "ASSIGN-RUN-VERIFY-001",
            },
            headers=auth_headers,
        )
    )
    assert assigned["assigned_specialist_id"] == "SPEC-DANIEL"
    assert assigned["assignment_run_id"] == "RUN-VERIFY-001"

    verified = assert_success(
        client.post(
            "/incident/api/v1/incidents/assignment/verify",
            json=assignment_verification_payload(),
            headers=auth_headers,
        )
    )
    assert verified["verified"] is True
    assert verified["result"] == "verified"
    assert verified["assignment_status"] == "active"
    assert verified["failed_checks"] == []

    wrong_specialist = assert_success(
        client.post(
            "/incident/api/v1/incidents/assignment/verify",
            json=assignment_verification_payload(expected_specialist_id="SPEC-MAYA"),
            headers=auth_headers,
        )
    )
    assert wrong_specialist["verified"] is False
    assert wrong_specialist["result"] == "inconsistent"
    assert "specialist_id_mismatch" in wrong_specialist["failed_checks"]

    wrong_run = assert_success(
        client.post(
            "/incident/api/v1/incidents/assignment/verify",
            json=assignment_verification_payload(expected_run_id="RUN-WRONG"),
            headers=auth_headers,
        )
    )
    assert wrong_run["verified"] is False
    assert "run_id_mismatch" in wrong_run["failed_checks"]


def test_verify_incident_assignment_unassigned_closed_and_unknown(client, auth_headers):
    unassigned = assert_success(
        client.post(
            "/incident/api/v1/incidents/assignment/verify",
            json=assignment_verification_payload(
                incident_id="INC-ALPHA-001",
                expected_run_id="RUN-VERIFY-UNASSIGNED",
                expected_specialist_id="SPEC-MAYA",
            ),
            headers=auth_headers,
        )
    )
    assert unassigned["verified"] is False
    assert unassigned["result"] == "pending"
    assert "incident_unassigned" in unassigned["failed_checks"]

    closed = assert_success(
        client.post(
            "/incident/api/v1/incidents/assignment/verify",
            json=assignment_verification_payload(
                incident_id="INC-OMEGA-001",
                expected_run_id="RUN-CLOSED",
                expected_specialist_id="SPEC-DANIEL",
            ),
            headers=auth_headers,
        )
    )
    assert closed["verified"] is False
    assert closed["result"] == "inconsistent"
    assert closed["assignment_status"] == "invalid"
    assert "assignment_status_invalid" in closed["failed_checks"]

    unknown = assert_success(
        client.post(
            "/incident/api/v1/incidents/assignment/verify",
            json=assignment_verification_payload(incident_id="INC-UNKNOWN"),
            headers=auth_headers,
        )
    )
    assert unknown["verified"] is False
    assert unknown["result"] == "not_found"
    assert unknown["actual_values"] is None


def test_admin_reset_auth_and_determinism(client, auth_headers, admin_headers, monkeypatch):
    assert_error(client.post("/admin/reset"), 401, "INCIDENT_401")
    assert_error(client.post("/admin/reset", headers={"X-Admin-Key": "wrong"}), 401, "INCIDENT_401")

    assert_success(
        client.post("/incident/api/v1/incidents", json=incident_payload(incident_id="INC-RESET-001"), headers=auth_headers),
        201,
    )
    reset = assert_success(client.post("/admin/reset", headers=admin_headers))
    assert reset["seeded_records"] == 9
    second_reset = assert_success(client.post("/admin/reset", headers=admin_headers))
    assert second_reset["seeded_records"] == 9
    assert_error(client.get("/incident/api/v1/incidents/INC-RESET-001", headers=auth_headers), 404, "INCIDENT_404")

    from app.config import get_settings

    monkeypatch.delenv("ADMIN_API_KEY", raising=False)
    get_settings.cache_clear()
    assert_error(client.post("/admin/reset", headers=admin_headers), 503, "INCIDENT_503")
    monkeypatch.setenv("ADMIN_API_KEY", "test-admin-key")
    get_settings.cache_clear()


def test_past_sla_deadline_is_allowed(client, auth_headers):
    created = assert_success(
        client.post(
            "/incident/api/v1/incidents",
            json=incident_payload(incident_id="INC-PAST-001", sla_deadline="2026-07-01T10:00:00Z"),
            headers=auth_headers,
        ),
        201,
    )
    assert datetime.fromisoformat(created["sla_deadline"].replace("Z", "+00:00")) < datetime.now(timezone.utc)


def test_simulation_load_state_update_and_resolve(client, auth_headers, admin_headers):
    load_payload = {
        "scenario_id": "scenario-test",
        "incidents": [
            {
                "incident_id": "inc-sim-001",
                "customer_id": "cus-alpha",
                "title": "Simulation incident",
                "description": "Simulation incident payload.",
                "priority": "medium",
                "status": "IN_PROGRESS",
                "sla_deadline": "2099-07-22T10:00:00Z",
                "estimated_effort_minutes": 60,
                "required_skills": ["Identity", " SAML "],
                "assigned_specialist_id": "spec-maya",
                "assigned_at": "2026-07-22T09:10:00Z",
                "created_at": "2026-07-22T09:00:00Z",
                "updated_at": "2026-07-22T09:10:00Z",
            }
        ],
    }
    loaded = client.post("/admin/simulation/load-state", json=load_payload, headers=admin_headers)
    assert loaded.status_code == 200
    assert assert_success(loaded)["incident_count"] == 1

    persisted = assert_success(
        client.get("/incident/api/v1/incidents/INC-SIM-001", headers=auth_headers)
    )
    assert persisted["required_skills"] == ["identity", "saml"]
    assert persisted["estimated_effort_minutes"] == 60

    updated = assert_success(
        client.patch(
            "/incident/api/v1/incidents/INC-SIM-001/simulation-fields",
            json={
                "priority": "critical",
                "sla_deadline": "2099-07-22T09:30:00Z",
                "estimated_effort_minutes": 90,
            },
            headers=auth_headers,
        )
    )
    assert updated["priority"] == "CRITICAL"
    assert updated["estimated_effort_minutes"] == 90

    resolved = assert_success(
        client.post(
            "/incident/api/v1/incidents/INC-SIM-001/simulation-resolve",
            json={"resolved_at": "2026-07-22T10:00:00Z", "resolution_note": "Done"},
            headers=auth_headers,
        )
    )
    assert resolved["status"] == "RESOLVED"
    assert resolved["assigned_specialist_id"] is None
    assert resolved["resolved_at"] == "2026-07-22T10:00:00Z"

    repeated = assert_success(
        client.post(
            "/incident/api/v1/incidents/INC-SIM-001/simulation-resolve",
            json={"resolved_at": "2026-07-22T10:00:00Z"},
            headers=auth_headers,
        )
    )
    assert repeated["status"] == "RESOLVED"

    assert_error(
        client.patch(
            "/incident/api/v1/incidents/INC-SIM-001/simulation-fields",
            json={"priority": "HIGH"},
            headers=auth_headers,
        ),
        409,
        "INCIDENT_409",
    )
