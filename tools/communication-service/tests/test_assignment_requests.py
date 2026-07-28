import time
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


def assignment_payload(**overrides):
    payload = {
        "request_id": "ar-test-001",
        "incident_id": "inc-test-001",
        "specialist_id": "spec-maya",
        "message": "Please review and accept this incident assignment.",
        "expires_in_seconds": 900,
    }
    payload.update(overrides)
    return payload


def response_payload(**overrides):
    payload = {"response": "ACCEPTED", "response_note": "I can take it."}
    payload.update(overrides)
    return payload


def test_health_readiness_and_docs(client):
    assert client.get("/health").json() == {"status": "healthy", "service": "communication-service"}
    readiness = client.get("/readiness")
    assert readiness.status_code == 200
    assert readiness.json()["database"] == "reachable"
    assert client.get("/docs").status_code == 200


def test_create_assignment_request_success_duplicate_and_validation(client, auth_headers):
    created = assert_success(
        client.post("/communication/api/v1/assignment-requests", json=assignment_payload(), headers=auth_headers),
        201,
    )
    assert created["request_id"] == "AR-TEST-001"
    assert created["incident_id"] == "INC-TEST-001"
    assert created["specialist_id"] == "SPEC-MAYA"
    assert created["run_id"] is None
    assert created["reservation_id"] is None
    assert created["idempotency_key"] is None
    assert created["status"] == "PENDING"
    assert created["responded_at"] is None

    assert_error(
        client.post("/communication/api/v1/assignment-requests", json=assignment_payload(), headers=auth_headers),
        409,
        "COMMUNICATION_409",
    )

    for overrides in [
        {"request_id": "   "},
        {"incident_id": "   "},
        {"specialist_id": "   "},
        {"message": "   "},
        {"expires_in_seconds": 29},
        {"expires_in_seconds": 86401},
        {"created_at": "2099-01-01T00:00:00Z"},
        {"message": "x" * 2001},
    ]:
        assert_error(
            client.post("/communication/api/v1/assignment-requests", json=assignment_payload(**overrides), headers=auth_headers),
            422,
            "COMMUNICATION_422",
        )


def test_create_assignment_request_idempotency_replay_and_payload_mismatch(client, auth_headers):
    payload = assignment_payload(
        request_id="AR-IDEM-001",
        incident_id="INC-IDEM-001",
        run_id="RUN-IDEM-001",
        reservation_id="RES-IDEM-001",
        idempotency_key="assign-idem-001",
    )
    created = assert_success(
        client.post("/communication/api/v1/assignment-requests", json=payload, headers=auth_headers),
        201,
    )
    replay = assert_success(
        client.post("/communication/api/v1/assignment-requests", json=payload, headers=auth_headers),
        200,
    )
    assert replay == created
    assert replay["run_id"] == "RUN-IDEM-001"
    assert replay["reservation_id"] == "RES-IDEM-001"
    assert replay["idempotency_key"] == "assign-idem-001"

    mismatch = dict(payload)
    mismatch["incident_id"] = "INC-IDEM-CHANGED"
    assert_error(
        client.post("/communication/api/v1/assignment-requests", json=mismatch, headers=auth_headers),
        409,
        "COMMUNICATION_409",
    )


def test_list_assignment_requests_filters_metadata_and_order(client, auth_headers):
    data = assert_success(client.get("/communication/api/v1/assignment-requests", headers=auth_headers))
    assert data["page"] == 1
    assert data["page_size"] == 20
    assert data["total_items"] == 5
    assert data["total_pages"] == 1
    assert [item["request_id"] for item in data["assignment_requests"]][:2] == [
        "AR-ACCEPTED-001",
        "AR-CANCELLED-001",
    ]

    page_two = assert_success(
        client.get("/communication/api/v1/assignment-requests?page=2&page_size=3", headers=auth_headers)
    )
    assert len(page_two["assignment_requests"]) == 2

    accepted = assert_success(
        client.get("/communication/api/v1/assignment-requests?status=accepted", headers=auth_headers)
    )
    assert [item["request_id"] for item in accepted["assignment_requests"]] == ["AR-ACCEPTED-001"]

    incident = assert_success(
        client.get("/communication/api/v1/assignment-requests?incident_id=inc-alpha-001", headers=auth_headers)
    )
    assert [item["request_id"] for item in incident["assignment_requests"]] == ["AR-PENDING-001"]

    specialist = assert_success(
        client.get("/communication/api/v1/assignment-requests?specialist_id=spec-nimal", headers=auth_headers)
    )
    assert [item["request_id"] for item in specialist["assignment_requests"]] == ["AR-REJECTED-001"]

    pending = assert_success(
        client.get("/communication/api/v1/assignment-requests?pending_only=true", headers=auth_headers)
    )
    assert [item["request_id"] for item in pending["assignment_requests"]] == ["AR-PENDING-001"]

    expired = assert_success(
        client.get("/communication/api/v1/assignment-requests?expired=true", headers=auth_headers)
    )
    assert [item["request_id"] for item in expired["assignment_requests"]] == ["AR-EXPIRED-001"]

    search = assert_success(client.get("/communication/api/v1/assignment-requests?search=payment", headers=auth_headers))
    assert [item["request_id"] for item in search["assignment_requests"]] == ["AR-PENDING-001"]

    assert_success(client.get("/communication/api/v1/assignment-requests?page=99", headers=auth_headers))[
        "assignment_requests"
    ] == []


def test_invalid_assignment_queries_use_standard_422(client, auth_headers):
    assert_error(client.get("/communication/api/v1/assignment-requests?page=0", headers=auth_headers), 422, "COMMUNICATION_422")
    assert_error(
        client.get("/communication/api/v1/assignment-requests?page_size=101", headers=auth_headers),
        422,
        "COMMUNICATION_422",
    )
    assert_error(
        client.get("/communication/api/v1/assignment-requests?status=waiting", headers=auth_headers),
        422,
        "COMMUNICATION_422",
    )
    assert_error(
        client.get(
            "/communication/api/v1/assignment-requests?created_after=2026-07-23T00:00:00Z&created_before=2026-07-22T00:00:00Z",
            headers=auth_headers,
        ),
        422,
        "COMMUNICATION_422",
    )


def test_get_assignment_existing_missing_and_expired(client, auth_headers):
    pending = assert_success(client.get("/communication/api/v1/assignment-requests/AR-PENDING-001", headers=auth_headers))
    assert pending["status"] == "PENDING"

    expired = assert_success(client.get("/communication/api/v1/assignment-requests/AR-EXPIRED-001", headers=auth_headers))
    assert expired["status"] == "EXPIRED"

    assert_error(
        client.get("/communication/api/v1/assignment-requests/AR-MISSING", headers=auth_headers),
        404,
        "COMMUNICATION_404",
    )


def test_respond_accept_reject_idempotent_and_conflict(client, auth_headers):
    created = assert_success(
        client.post(
            "/communication/api/v1/assignment-requests",
            json=assignment_payload(request_id="AR-RESPOND-001", incident_id="INC-RESPOND-001"),
            headers=auth_headers,
        ),
        201,
    )
    accepted = assert_success(
        client.post(
            f"/communication/api/v1/assignment-requests/{created['request_id']}/respond",
            json=response_payload(response="accepted", response_note="First note"),
            headers=auth_headers,
        )
    )
    assert accepted["status"] == "ACCEPTED"
    assert accepted["responded_at"] is not None
    assert accepted["response_note"] == "First note"
    assert accepted["response_reason"] == "First note"

    repeat = assert_success(
        client.post(
            f"/communication/api/v1/assignment-requests/{created['request_id']}/respond",
            json=response_payload(response="ACCEPTED", response_note="Different note"),
            headers=auth_headers,
        )
    )
    assert repeat["status"] == "ACCEPTED"
    assert repeat["response_note"] == "First note"

    assert_error(
        client.post(
            f"/communication/api/v1/assignment-requests/{created['request_id']}/respond",
            json=response_payload(response="REJECTED"),
            headers=auth_headers,
        ),
        409,
        "COMMUNICATION_409",
    )

    rejected_request = assert_success(
        client.post(
            "/communication/api/v1/assignment-requests",
            json=assignment_payload(request_id="AR-RESPOND-002", incident_id="INC-RESPOND-002"),
            headers=auth_headers,
        ),
        201,
    )
    rejected = assert_success(
        client.post(
            f"/communication/api/v1/assignment-requests/{rejected_request['request_id']}/respond",
            json=response_payload(response="REJECTED", response_note="No capacity"),
            headers=auth_headers,
        )
    )
    assert rejected["status"] == "REJECTED"


def assignment_verification_payload(**overrides):
    payload = {
        "assignment_request_id": "AR-VERIFY-OK",
        "expected_run_id": "RUN-VERIFY-001",
        "expected_incident_id": "INC-VERIFY-001",
        "expected_specialist_id": "SPEC-MAYA",
        "expected_status": "ACCEPTED",
    }
    payload.update(overrides)
    return payload


def test_verify_assignment_request_accepted_and_mismatches(client, auth_headers):
    created = assert_success(
        client.post(
            "/communication/api/v1/assignment-requests",
            json=assignment_payload(
                request_id="AR-VERIFY-OK",
                incident_id="INC-VERIFY-001",
                run_id="RUN-VERIFY-001",
            ),
            headers=auth_headers,
        ),
        201,
    )
    assert_success(
        client.post(
            f"/communication/api/v1/assignment-requests/{created['request_id']}/respond",
            json=response_payload(response="ACCEPTED"),
            headers=auth_headers,
        )
    )

    verified = assert_success(
        client.post(
            "/communication/api/v1/assignment-requests/verify",
            json=assignment_verification_payload(),
            headers=auth_headers,
        )
    )
    assert verified["verified"] is True
    assert verified["result"] == "verified"
    assert verified["current_status"] == "ACCEPTED"
    assert verified["failed_checks"] == []

    wrong_specialist = assert_success(
        client.post(
            "/communication/api/v1/assignment-requests/verify",
            json=assignment_verification_payload(expected_specialist_id="SPEC-DANIEL"),
            headers=auth_headers,
        )
    )
    assert wrong_specialist["verified"] is False
    assert wrong_specialist["result"] == "inconsistent"
    assert "specialist_id_mismatch" in wrong_specialist["failed_checks"]

    wrong_incident = assert_success(
        client.post(
            "/communication/api/v1/assignment-requests/verify",
            json=assignment_verification_payload(expected_incident_id="INC-WRONG"),
            headers=auth_headers,
        )
    )
    assert wrong_incident["verified"] is False
    assert "incident_id_mismatch" in wrong_incident["failed_checks"]


def test_verify_assignment_request_pending_rejected_expired_and_unknown(client, auth_headers):
    pending_request = assert_success(
        client.post(
            "/communication/api/v1/assignment-requests",
            json=assignment_payload(
                request_id="AR-VERIFY-PENDING",
                incident_id="INC-VERIFY-PENDING",
                run_id="RUN-VERIFY-PENDING",
            ),
            headers=auth_headers,
        ),
        201,
    )
    pending = assert_success(
        client.post(
            "/communication/api/v1/assignment-requests/verify",
            json=assignment_verification_payload(
                assignment_request_id=pending_request["request_id"],
                expected_run_id="RUN-VERIFY-PENDING",
                expected_incident_id="INC-VERIFY-PENDING",
            ),
            headers=auth_headers,
        )
    )
    assert pending["verified"] is False
    assert pending["result"] == "pending"
    assert "request_pending" in pending["failed_checks"]

    rejected_request = assert_success(
        client.post(
            "/communication/api/v1/assignment-requests",
            json=assignment_payload(
                request_id="AR-VERIFY-REJECTED",
                incident_id="INC-VERIFY-REJECTED",
                run_id="RUN-VERIFY-REJECTED",
            ),
            headers=auth_headers,
        ),
        201,
    )
    assert_success(
        client.post(
            f"/communication/api/v1/assignment-requests/{rejected_request['request_id']}/respond",
            json=response_payload(response="REJECTED"),
            headers=auth_headers,
        )
    )
    rejected = assert_success(
        client.post(
            "/communication/api/v1/assignment-requests/verify",
            json=assignment_verification_payload(
                assignment_request_id=rejected_request["request_id"],
                expected_run_id="RUN-VERIFY-REJECTED",
                expected_incident_id="INC-VERIFY-REJECTED",
            ),
            headers=auth_headers,
        )
    )
    assert rejected["verified"] is False
    assert rejected["result"] == "rejected"
    assert "request_rejected" in rejected["failed_checks"]

    expired = assert_success(
        client.post(
            "/communication/api/v1/assignment-requests/verify",
            json=assignment_verification_payload(
                assignment_request_id="AR-EXPIRED-001",
                expected_run_id="RUN-EXPIRED",
                expected_incident_id="INC-EXPIRED-001",
                expected_specialist_id="SPEC-PRIYA",
            ),
            headers=auth_headers,
        )
    )
    assert expired["verified"] is False
    assert expired["result"] == "expired"
    assert "request_expired" in expired["failed_checks"]

    unknown = assert_success(
        client.post(
            "/communication/api/v1/assignment-requests/verify",
            json=assignment_verification_payload(assignment_request_id="AR-UNKNOWN"),
            headers=auth_headers,
        )
    )
    assert unknown["verified"] is False
    assert unknown["result"] == "not_found"
    assert unknown["actual_values"] is None


def test_admin_queued_accept_reject_delay_and_one_time_consumption(client, auth_headers, admin_headers):
    accepted_config = assert_success(
        client.post(
            "/admin/next-response",
            json={
                "specialist_id": "SPEC-MAYA",
                "incident_id": "INC-QUEUE-ACCEPT",
                "status": "ACCEPTED",
                "reason": "Queued acceptance",
            },
            headers=admin_headers,
        )
    )
    assert accepted_config["status"] == "ACCEPTED"
    assert accepted_config["apply_once"] is True
    assert accepted_config["simulation_rule_id"] >= 1
    assert accepted_config["active"] is True

    created = assert_success(
        client.post(
            "/communication/api/v1/assignment-requests",
            json=assignment_payload(request_id="AR-QUEUE-ACCEPT", incident_id="INC-QUEUE-ACCEPT"),
            headers=auth_headers,
        ),
        201,
    )
    assert created["status"] == "PENDING"
    accepted = assert_success(
        client.get("/communication/api/v1/assignment-requests/AR-QUEUE-ACCEPT", headers=auth_headers)
    )
    assert accepted["status"] == "ACCEPTED"
    assert accepted["response_reason"] == "Queued acceptance"

    assert_success(
        client.post(
            "/admin/next-response",
            json={
                "specialist_id": "SPEC-MAYA",
                "incident_id": "INC-QUEUE-REJECT",
                "status": "REJECTED",
                "reason": "Queued rejection",
            },
            headers=admin_headers,
        )
    )
    assert_success(
        client.post(
            "/communication/api/v1/assignment-requests",
            json=assignment_payload(request_id="AR-QUEUE-REJECT", incident_id="INC-QUEUE-REJECT"),
            headers=auth_headers,
        ),
        201,
    )
    rejected = assert_success(
        client.get("/communication/api/v1/assignment-requests/AR-QUEUE-REJECT", headers=auth_headers)
    )
    assert rejected["status"] == "REJECTED"
    assert rejected["response_reason"] == "Queued rejection"

    assert_success(
        client.post(
            "/admin/next-response",
            json={
                "specialist_id": "SPEC-MAYA",
                "status": "ACCEPTED",
                "reason": "One time only",
            },
            headers=admin_headers,
        )
    )
    assert_success(
        client.post(
            "/communication/api/v1/assignment-requests",
            json=assignment_payload(request_id="AR-ONCE-001", incident_id="INC-ONCE-001"),
            headers=auth_headers,
        ),
        201,
    )
    first = assert_success(client.get("/communication/api/v1/assignment-requests/AR-ONCE-001", headers=auth_headers))
    assert first["status"] == "ACCEPTED"
    assert_success(
        client.post(
            "/communication/api/v1/assignment-requests",
            json=assignment_payload(request_id="AR-ONCE-002", incident_id="INC-ONCE-002"),
            headers=auth_headers,
        ),
        201,
    )
    second = assert_success(client.get("/communication/api/v1/assignment-requests/AR-ONCE-002", headers=auth_headers))
    assert second["status"] == "PENDING"

    assert_success(
        client.post(
            "/admin/next-response",
            json={
                "specialist_id": "SPEC-MAYA",
                "status": "REJECTED",
                "reason": "Persistent rejection",
                "apply_once": False,
            },
            headers=admin_headers,
        )
    )
    for index in (1, 2):
        assert_success(
            client.post(
                "/communication/api/v1/assignment-requests",
                json=assignment_payload(request_id=f"AR-PERSIST-{index}", incident_id=f"INC-PERSIST-{index}"),
                headers=auth_headers,
            ),
            201,
        )
        persistent = assert_success(
            client.get(f"/communication/api/v1/assignment-requests/AR-PERSIST-{index}", headers=auth_headers)
        )
        assert persistent["status"] == "REJECTED"

    assert_success(
        client.post(
            "/admin/next-response",
            json={
                "specialist_id": "SPEC-MAYA",
                "incident_id": "INC-DELAY-001",
                "status": "ACCEPTED",
                "reason": "Delayed acceptance",
                "response_delay_seconds": 1,
            },
            headers=admin_headers,
        )
    )
    assert_success(
        client.post(
            "/communication/api/v1/assignment-requests",
            json=assignment_payload(request_id="AR-DELAY-001", incident_id="INC-DELAY-001"),
            headers=auth_headers,
        ),
        201,
    )
    pending = assert_success(client.get("/communication/api/v1/assignment-requests/AR-DELAY-001", headers=auth_headers))
    assert pending["status"] == "PENDING"
    time.sleep(1.1)
    delayed = assert_success(client.get("/communication/api/v1/assignment-requests/AR-DELAY-001", headers=auth_headers))
    assert delayed["status"] == "ACCEPTED"

    assert_success(
        client.post(
            "/admin/next-response",
            json={
                "specialist_id": "SPEC-DANIEL",
                "incident_id": "INC-EXPIRED-RULE",
                "status": "ACCEPTED",
                "expires_after_seconds": 1,
            },
            headers=admin_headers,
        )
    )
    time.sleep(1.1)
    assert_success(
        client.post(
            "/communication/api/v1/assignment-requests",
            json=assignment_payload(
                request_id="AR-EXPIRED-RULE",
                incident_id="INC-EXPIRED-RULE",
                specialist_id="SPEC-DANIEL",
            ),
            headers=auth_headers,
        ),
        201,
    )
    expired_rule = assert_success(
        client.get("/communication/api/v1/assignment-requests/AR-EXPIRED-RULE", headers=auth_headers)
    )
    assert expired_rule["status"] == "PENDING"


def test_admin_failure_mode_enable_disable(client, auth_headers, admin_headers):
    initial = assert_success(client.get("/admin/failure-mode", headers=admin_headers))
    assert initial["enabled"] is False
    assert initial["active_rules"] == []

    enabled = assert_success(
        client.post(
            "/admin/failure-mode",
            json={
                "enabled": True,
                "failure_type": "HTTP_ERROR",
                "status_code": 503,
                "affected_endpoint": "assignment:get",
            },
            headers=admin_headers,
        )
    )
    assert enabled["enabled"] is True
    assert enabled["simulation_rule_id"] >= 1
    assert_error(
        client.get("/communication/api/v1/assignment-requests/AR-PENDING-001", headers=auth_headers),
        503,
        "COMMUNICATION_503",
    )

    disabled = assert_success(client.post("/admin/failure-mode", json={"enabled": False}, headers=admin_headers))
    assert disabled["enabled"] is False
    assert_success(client.get("/communication/api/v1/assignment-requests/AR-PENDING-001", headers=auth_headers))


def test_admin_failure_modes_one_time_delay_timeout_and_state(client, auth_headers, admin_headers):
    assert_error(
        client.post(
            "/admin/failure-mode",
            json={"enabled": True, "failure_type": "NOT_SUPPORTED"},
            headers=admin_headers,
        ),
        422,
        "COMMUNICATION_422",
    )

    one_time = assert_success(
        client.post(
            "/admin/failure-mode",
            json={
                "enabled": True,
                "failure_type": "HTTP_ERROR",
                "status_code": 502,
                "affected_endpoint": "assignment:get",
                "apply_once": True,
                "message": "One failure only",
            },
            headers=admin_headers,
        )
    )
    assert one_time["remaining_uses"] == 1
    assert_error(
        client.get("/communication/api/v1/assignment-requests/AR-PENDING-001", headers=auth_headers),
        502,
        "COMMUNICATION_502",
    )
    assert_success(client.get("/communication/api/v1/assignment-requests/AR-PENDING-001", headers=auth_headers))

    timeout = assert_success(
        client.post(
            "/admin/failure-mode",
            json={
                "enabled": True,
                "failure_type": "TIMEOUT",
                "affected_endpoint": "assignment:get",
                "apply_once": True,
            },
            headers=admin_headers,
        )
    )
    assert timeout["failure_type"] == "TIMEOUT"
    assert_error(
        client.get("/communication/api/v1/assignment-requests/AR-PENDING-001", headers=auth_headers),
        504,
        "COMMUNICATION_504",
    )

    delay = assert_success(
        client.post(
            "/admin/failure-mode",
            json={
                "enabled": True,
                "failure_type": "DELAY",
                "delay_seconds": 1,
                "affected_endpoint": "assignment:get",
                "apply_once": True,
            },
            headers=admin_headers,
        )
    )
    assert delay["failure_type"] == "DELAY"
    started = time.perf_counter()
    assert_success(client.get("/communication/api/v1/assignment-requests/AR-PENDING-001", headers=auth_headers))
    assert time.perf_counter() - started >= 1

    assert_success(
        client.post(
            "/admin/next-response",
            json={"specialist_id": "SPEC-MAYA", "status": "ACCEPTED", "reason": "State visible"},
            headers=admin_headers,
        )
    )
    state = assert_success(client.get("/admin/simulation-state", headers=admin_headers))
    assert "queued_specialist_responses" in state
    assert "active_failure_modes" in state
    assert any(item["request_id"] == "AR-PENDING-001" for item in state["pending_assignment_requests"])

    reset = assert_success(client.post("/admin/reset", headers=admin_headers))
    assert reset == {"assignment_request_count": 5, "notification_count": 5}
    state_after_reset = assert_success(client.get("/admin/simulation-state", headers=admin_headers))
    assert state_after_reset["queued_specialist_responses"] == []
    assert state_after_reset["active_failure_modes"] == []
    assert state_after_reset["last_reset_at"] is not None


def test_respond_rejects_invalid_missing_expired_and_cancelled(client, auth_headers):
    assert_error(
        client.post(
            "/communication/api/v1/assignment-requests/AR-PENDING-001/respond",
            json=response_payload(response="MAYBE"),
            headers=auth_headers,
        ),
        422,
        "COMMUNICATION_422",
    )
    assert_error(
        client.post(
            "/communication/api/v1/assignment-requests/AR-MISSING/respond",
            json=response_payload(),
            headers=auth_headers,
        ),
        404,
        "COMMUNICATION_404",
    )
    assert_error(
        client.post(
            "/communication/api/v1/assignment-requests/AR-EXPIRED-001/respond",
            json=response_payload(),
            headers=auth_headers,
        ),
        409,
        "COMMUNICATION_409",
    )
    assert_error(
        client.post(
            "/communication/api/v1/assignment-requests/AR-CANCELLED-001/respond",
            json=response_payload(),
            headers=auth_headers,
        ),
        409,
        "COMMUNICATION_409",
    )


def test_assignment_auth_legacy_routes_and_utc_timestamps(client, auth_headers):
    assert_error(client.get("/communication/api/v1/assignment-requests"), 401, "COMMUNICATION_401")
    legacy_list = client.get("/assignment-requests", headers=auth_headers)
    assert legacy_list.status_code == 200
    assert any(item["requestId"] == "AR-PENDING-001" for item in legacy_list.json())

    legacy_created = client.post(
        "/assignment-requests",
        json={"specialistId": "SPEC-MAYA", "escalationId": "INC-LEGACY-001", "idempotencyKey": "AR-LEGACY-001"},
        headers=auth_headers,
    )
    assert legacy_created.status_code == 200
    assert legacy_created.json()["requestId"] == "AR-LEGACY-001"

    legacy_response = client.post(
        "/assignment-requests/AR-LEGACY-001/respond",
        json={"status": "ACCEPTED", "reason": "Legacy accepted"},
        headers=auth_headers,
    )
    assert legacy_response.status_code == 200

    data = assert_success(client.get("/communication/api/v1/assignment-requests/AR-LEGACY-001", headers=auth_headers))
    assert datetime.fromisoformat(data["created_at"].replace("Z", "+00:00")).tzinfo == timezone.utc
