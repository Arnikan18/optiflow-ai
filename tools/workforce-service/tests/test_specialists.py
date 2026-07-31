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


def reservation_payload(**overrides):
    payload = {
        "reservation_id": "res-test-001",
        "specialist_id": "spec-daniel",
        "incident_id": "inc-test-001",
        "expires_in_seconds": 300,
    }
    payload.update(overrides)
    return payload


def test_health_readiness_and_docs(client):
    assert client.get("/health").json() == {"status": "healthy", "service": "workforce-service"}
    readiness = client.get("/readiness")
    assert readiness.status_code == 200
    assert readiness.json()["database"] == "reachable"
    assert client.get("/docs").status_code == 200


def test_list_specialists_default_pagination_and_legacy_route(client, auth_headers):
    data = assert_success(client.get("/workforce/api/v1/specialists", headers=auth_headers))
    assert data["page"] == 1
    assert data["page_size"] == 20
    assert data["total_items"] == 8
    assert [item["specialist_id"] for item in data["specialists"]] == [
        "SPEC-DANIEL",
        "SPEC-KAI",
        "SPEC-LEILA",
        "SPEC-MAYA",
        "SPEC-NIMAL",
        "SPEC-OMAR",
        "SPEC-PRIYA",
        "SPEC-SOFIA",
    ]

    page_two = assert_success(client.get("/workforce/api/v1/specialists?page=2&page_size=3", headers=auth_headers))
    assert [item["specialist_id"] for item in page_two["specialists"]] == [
        "SPEC-MAYA",
        "SPEC-NIMAL",
        "SPEC-OMAR",
    ]

    beyond = assert_success(client.get("/workforce/api/v1/specialists?page=99", headers=auth_headers))
    assert beyond["specialists"] == []

    legacy = client.get("/specialists", headers=auth_headers)
    assert legacy.status_code == 200
    assert {item["specialistId"] for item in legacy.json()} == {
        "SPEC-MAYA",
        "SPEC-DANIEL",
        "SPEC-NIMAL",
        "SPEC-PRIYA",
        "SPEC-KAI",
        "SPEC-LEILA",
        "SPEC-OMAR",
        "SPEC-SOFIA",
    }


def test_specialist_filters_and_search(client, auth_headers):
    active = assert_success(client.get("/workforce/api/v1/specialists?active=true", headers=auth_headers))
    assert active["total_items"] == 7

    unavailable = assert_success(client.get("/workforce/api/v1/specialists?availability=false", headers=auth_headers))
    assert [item["specialist_id"] for item in unavailable["specialists"]] == [
        "SPEC-PRIYA",
        "SPEC-SOFIA",
    ]

    billing = assert_success(client.get("/workforce/api/v1/specialists?skill= Billing ", headers=auth_headers))
    assert [item["specialist_id"] for item in billing["specialists"]] == ["SPEC-MAYA", "SPEC-PRIYA"]

    min_capacity = assert_success(
        client.get("/workforce/api/v1/specialists?min_available_capacity=2", headers=auth_headers)
    )
    assert {item["specialist_id"] for item in min_capacity["specialists"]} == {
        "SPEC-KAI",
        "SPEC-LEILA",
        "SPEC-MAYA",
        "SPEC-OMAR",
        "SPEC-PRIYA",
        "SPEC-SOFIA",
    }

    by_id = assert_success(client.get("/workforce/api/v1/specialists?search=daniel", headers=auth_headers))
    assert [item["specialist_id"] for item in by_id["specialists"]] == ["SPEC-DANIEL"]

    no_match = assert_success(client.get("/workforce/api/v1/specialists?skill=unknown", headers=auth_headers))
    assert no_match["total_items"] == 0


def test_available_specialists_filters_capacity_and_pending_counts(client, auth_headers):
    available = assert_success(client.get("/workforce/api/v1/specialists/available", headers=auth_headers))
    assert [item["specialist_id"] for item in available["specialists"]] == [
        "SPEC-DANIEL",
        "SPEC-LEILA",
        "SPEC-MAYA",
        "SPEC-OMAR",
    ]

    technical = assert_success(
        client.get("/workforce/api/v1/specialists/available?skill=technical", headers=auth_headers)
    )
    assert [item["specialist_id"] for item in technical["specialists"]] == [
        "SPEC-DANIEL",
        "SPEC-MAYA",
        "SPEC-OMAR",
    ]

    required_two = assert_success(
        client.get("/workforce/api/v1/specialists/available?required_capacity=2", headers=auth_headers)
    )
    assert [item["specialist_id"] for item in required_two["specialists"]] == [
        "SPEC-LEILA",
        "SPEC-MAYA",
        "SPEC-OMAR",
    ]

    maya = assert_success(client.get("/workforce/api/v1/specialists/SPEC-MAYA", headers=auth_headers))
    assert maya["current_workload"] == 0
    assert maya["effective_workload"] == 0
    assert maya["available_capacity"] == 2
    assert maya["operationally_available"] is True
    assert maya["completed_assignments_30d"] == 38
    assert maya["sla_success_rate_30d"] == 96.0
    assert maya["average_resolution_minutes_30d"] == 72
    assert maya["assignment_acceptance_rate_30d"] == 94.0
    assert maya["capacity_reliability_rate_30d"] == 97.0


def test_list_workloads_exposes_reservation_counts(client, auth_headers):
    data = assert_success(client.get("/workforce/api/v1/workloads", headers=auth_headers))
    assert data["page"] == 1
    assert data["total_items"] == 8

    workloads = {item["specialist_id"]: item for item in data["workloads"]}
    assert workloads["SPEC-MAYA"]["assigned_count"] == 0
    assert workloads["SPEC-MAYA"]["tentative_reservation_count"] == 0
    assert workloads["SPEC-MAYA"]["confirmed_reservation_count"] == 0
    assert workloads["SPEC-MAYA"]["available_capacity"] == 2
    assert workloads["SPEC-MAYA"]["utilisation_percentage"] == 0.0

    assert workloads["SPEC-DANIEL"]["assigned_count"] == 1
    assert workloads["SPEC-DANIEL"]["confirmed_reservation_count"] == 1
    assert workloads["SPEC-LEILA"]["assigned_count"] == 1
    assert workloads["SPEC-LEILA"]["available_capacity"] == 2
    assert workloads["SPEC-OMAR"]["tentative_reservation_count"] == 0
    assert workloads["SPEC-OMAR"]["available_capacity"] == 3


def test_get_specialist_existing_missing_inactive_and_full_capacity(client, auth_headers):
    inactive = assert_success(client.get("/workforce/api/v1/specialists/spec-kai", headers=auth_headers))
    assert inactive["active"] is False
    assert inactive["available_capacity"] == 2
    assert inactive["operationally_available"] is False

    full = assert_success(client.get("/workforce/api/v1/specialists/SPEC-NIMAL", headers=auth_headers))
    assert full["current_workload"] == full["capacity"]
    assert full["available_capacity"] == 0

    assert_error(client.get("/workforce/api/v1/specialists/SPEC-MISSING", headers=auth_headers), 404, "WORKFORCE_404")


def test_invalid_specialist_queries_use_standard_422(client, auth_headers):
    assert_error(client.get("/workforce/api/v1/specialists?page=0", headers=auth_headers), 422, "WORKFORCE_422")
    assert_error(client.get("/workforce/api/v1/specialists?page_size=101", headers=auth_headers), 422, "WORKFORCE_422")
    assert_error(
        client.get("/workforce/api/v1/specialists?min_available_capacity=-1", headers=auth_headers),
        422,
        "WORKFORCE_422",
    )
    assert_error(
        client.get("/workforce/api/v1/specialists/available?required_capacity=0", headers=auth_headers),
        422,
        "WORKFORCE_422",
    )


def test_legacy_availability_and_workload(client, auth_headers):
    availability = client.get("/availability", headers=auth_headers)
    assert availability.status_code == 200
    assert {item["specialistId"] for item in availability.json()["specialists"]} == {
        "SPEC-DANIEL",
        "SPEC-LEILA",
        "SPEC-MAYA",
        "SPEC-OMAR",
    }

    workload = client.get("/workload", headers=auth_headers)
    assert workload.status_code == 200
    assert {item["specialistId"] for item in workload.json()} == {
        "SPEC-MAYA",
        "SPEC-DANIEL",
        "SPEC-NIMAL",
        "SPEC-PRIYA",
        "SPEC-KAI",
        "SPEC-LEILA",
        "SPEC-OMAR",
        "SPEC-SOFIA",
    }


def test_legacy_admin_workload_accepts_camel_case(client, auth_headers):
    response = client.post(
        "/admin/workload/SPEC-MAYA",
        json={"activeAssignmentCount": 1, "afterHoursMinutes": 30},
        headers=auth_headers,
    )
    assert response.status_code == 200

    specialist = assert_success(client.get("/workforce/api/v1/specialists/SPEC-MAYA", headers=auth_headers))
    assert specialist["current_workload"] == 1


def test_response_timestamps_are_utc(client, auth_headers):
    data = assert_success(client.get("/workforce/api/v1/specialists/SPEC-DANIEL", headers=auth_headers))
    assert datetime.fromisoformat(data["created_at"].replace("Z", "+00:00")).tzinfo == timezone.utc


def test_simulation_load_availability_and_release_workload(client, auth_headers, admin_headers):
    load_payload = {
        "scenario_id": "scenario-test",
        "specialists": [
            {
                "specialist_id": "spec-sim-001",
                "name": "Simulation Specialist",
                "email": "simulation.specialist@example.test",
                "skills": ["technical"],
                "capacity": 2,
                "current_workload": 1,
                "availability": True,
                "active": True,
                "completed_assignments_30d": 14,
                "sla_success_rate_30d": 92.5,
                "average_resolution_minutes_30d": 86,
                "assignment_acceptance_rate_30d": 90.0,
                "capacity_reliability_rate_30d": 96.0,
                "created_at": "2026-07-22T09:00:00Z",
                "updated_at": "2026-07-22T09:00:00Z",
            }
        ],
        "reservations": [
            {
                "reservation_id": "res-sim-001",
                "run_id": "run-sim",
                "specialist_id": "spec-sim-001",
                "incident_id": "inc-sim-001",
                "status": "CONFIRMED",
                "idempotency_key": "res-sim-001",
                "created_at": "2026-07-22T09:00:00Z",
                "expires_at": "2026-07-22T09:30:00Z",
                "confirmed_at": "2026-07-22T09:01:00Z",
                "updated_at": "2026-07-22T09:01:00Z",
            }
        ],
    }

    loaded = client.post("/admin/simulation/load-state", json=load_payload, headers=admin_headers)
    assert loaded.status_code == 200
    assert assert_success(loaded)["specialist_count"] == 1

    persisted = assert_success(
        client.get("/workforce/api/v1/specialists/SPEC-SIM-001", headers=auth_headers)
    )
    assert persisted["completed_assignments_30d"] == 14
    assert persisted["sla_success_rate_30d"] == 92.5
    assert persisted["average_resolution_minutes_30d"] == 86

    unavailable = assert_success(
        client.patch(
            "/workforce/api/v1/specialists/SPEC-SIM-001/simulation-availability",
            json={"availability": False, "reason": "leave"},
            headers=auth_headers,
        )
    )
    assert unavailable["availability"] is False
    assert unavailable["operationally_available"] is False

    capacity = assert_success(
        client.patch(
            "/workforce/api/v1/specialists/SPEC-SIM-001/simulation-capacity",
            json={"capacity": 3, "current_workload": 2, "reason": "live demo"},
            headers=auth_headers,
        )
    )
    assert capacity["capacity"] == 3
    assert capacity["current_workload"] == 2
    assert capacity["available_capacity"] == 1

    conflict = client.patch(
        "/workforce/api/v1/specialists/SPEC-SIM-001/simulation-capacity",
        json={"capacity": 1},
        headers=auth_headers,
    )
    assert conflict.status_code == 409
    assert conflict.json()["errorCode"] == "WORKFORCE_CAPACITY_CONFLICT"

    released = assert_success(
        client.post(
            "/workforce/api/v1/incidents/INC-SIM-001/release-workload",
            json={"reason": "resolved"},
            headers=auth_headers,
        )
    )
    assert released["released_reservations"] == 1
    assert released["reservation_ids"] == ["RES-SIM-001"]

    specialist = assert_success(client.get("/workforce/api/v1/specialists/SPEC-SIM-001", headers=auth_headers))
    assert specialist["current_workload"] == 1
