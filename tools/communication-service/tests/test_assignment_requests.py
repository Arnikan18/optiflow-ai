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
