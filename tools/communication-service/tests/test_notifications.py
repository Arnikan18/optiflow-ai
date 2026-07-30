from tests.test_assignment_requests import assert_error, assert_success


def notification_payload(**overrides):
    payload = {
        "notification_id": "not-test-001",
        "recipient": "specialist@example.test",
        "channel": "EMAIL",
        "subject": "New Incident Assignment",
        "message": "You have received a new incident assignment request.",
        "related_request_id": "AR-PENDING-001",
        "idempotency_key": "notify-test-001",
    }
    payload.update(overrides)
    return payload


def test_create_notifications_for_supported_channels(client, auth_headers):
    email = assert_success(
        client.post("/communication/api/v1/notifications", json=notification_payload(), headers=auth_headers),
        201,
    )
    assert email["notification_id"] == "NOT-TEST-001"
    assert email["channel"] == "EMAIL"
    assert email["status"] == "DELIVERED"
    assert email["attempt_count"] == 1
    assert email["attempted_at"] is not None
    assert email["delivered_at"] is not None

    sms = assert_success(
        client.post(
            "/communication/api/v1/notifications",
            json=notification_payload(
                notification_id="not-test-sms",
                recipient="+15550101111",
                channel="sms",
                subject=None,
                idempotency_key="notify-test-sms",
            ),
            headers=auth_headers,
        ),
        201,
    )
    assert sms["channel"] == "SMS"
    assert sms["status"] == "DELIVERED"

    in_app = assert_success(
        client.post(
            "/communication/api/v1/notifications",
            json=notification_payload(
                notification_id="not-test-inapp",
                recipient="SPEC-MAYA",
                channel="IN_APP",
                subject="Assignment update",
                idempotency_key="notify-test-inapp",
            ),
            headers=auth_headers,
        ),
        201,
    )
    assert in_app["channel"] == "IN_APP"

    webhook = assert_success(
        client.post(
            "/communication/api/v1/notifications",
            json=notification_payload(
                notification_id="not-test-webhook",
                recipient="webhook-demo-destination",
                channel="WEBHOOK",
                subject="Portfolio event",
                related_request_id=None,
                idempotency_key="notify-test-webhook",
            ),
            headers=auth_headers,
        ),
        201,
    )
    assert webhook["channel"] == "WEBHOOK"


def test_notification_validation_and_duplicate_conflicts(client, auth_headers):
    assert_success(
        client.post("/communication/api/v1/notifications", json=notification_payload(), headers=auth_headers),
        201,
    )
    assert_error(
        client.post(
            "/communication/api/v1/notifications",
            json=notification_payload(idempotency_key="another-key"),
            headers=auth_headers,
        ),
        409,
        "COMMUNICATION_409",
    )

    for index, overrides in enumerate(
        [
        {"notification_id": "   "},
        {"recipient": "   "},
        {"recipient": "not-an-email"},
        {"recipient": "5550101", "channel": "SMS", "subject": None},
        {"channel": "PAGER"},
        {"message": "   "},
        {"subject": None},
        {"created_at": "2099-01-01T00:00:00Z"},
        {"related_request_id": "AR-MISSING"},
        ],
        start=1,
    ):
        expected_status = 404 if overrides.get("related_request_id") == "AR-MISSING" else 422
        expected_code = "COMMUNICATION_404" if expected_status == 404 else "COMMUNICATION_422"
        payload = notification_payload(
            notification_id=f"not-validation-{index}",
            idempotency_key=f"notify-validation-{index}",
        )
        payload.update(overrides)
        assert_error(
            client.post(
                "/communication/api/v1/notifications",
                json=payload,
                headers=auth_headers,
            ),
            expected_status,
            expected_code,
        )


def test_notification_idempotency_replay_and_payload_mismatch(client, auth_headers):
    payload = notification_payload(notification_id="not-idem-001", idempotency_key="notify-idem-001")
    created = assert_success(client.post("/communication/api/v1/notifications", json=payload, headers=auth_headers), 201)

    replay = assert_success(client.post("/communication/api/v1/notifications", json=payload, headers=auth_headers), 200)
    assert replay["notification_id"] == created["notification_id"]

    mismatch = dict(payload)
    mismatch["message"] = "Different message"
    assert_error(
        client.post("/communication/api/v1/notifications", json=mismatch, headers=auth_headers),
        409,
        "COMMUNICATION_409",
    )


def test_simulated_delivery_failure_is_persisted_not_500(client, auth_headers):
    failed = assert_success(
        client.post(
            "/communication/api/v1/notifications",
            json=notification_payload(
                notification_id="not-fail-001",
                recipient="fail@example.test",
                idempotency_key="notify-fail-001",
            ),
            headers=auth_headers,
        ),
        201,
    )
    assert failed["status"] == "FAILED"
    assert failed["attempt_count"] == 1
    assert failed["attempted_at"] is not None
    assert failed["delivered_at"] is None
    assert failed["failure_reason"] == "Simulated delivery failed"


def test_list_notifications_filters_metadata_and_order(client, auth_headers):
    data = assert_success(client.get("/communication/api/v1/notifications", headers=auth_headers))
    assert data["page"] == 1
    assert data["page_size"] == 20
    assert data["total_items"] == 5
    assert [item["notification_id"] for item in data["notifications"]][:2] == [
        "NOT-EMAIL-DELIVERED",
        "NOT-FAILED-001",
    ]

    page_two = assert_success(client.get("/communication/api/v1/notifications?page=2&page_size=3", headers=auth_headers))
    assert len(page_two["notifications"]) == 2

    delivered = assert_success(client.get("/communication/api/v1/notifications?status=delivered", headers=auth_headers))
    assert delivered["total_items"] == 4

    email = assert_success(client.get("/communication/api/v1/notifications?channel=email", headers=auth_headers))
    assert {item["notification_id"] for item in email["notifications"]} == {"NOT-EMAIL-DELIVERED", "NOT-FAILED-001"}

    related = assert_success(
        client.get("/communication/api/v1/notifications?related_request_id=ar-accepted-001", headers=auth_headers)
    )
    assert {item["notification_id"] for item in related["notifications"]} == {
        "NOT-INAPP-DELIVERED",
        "NOT-SMS-DELIVERED",
    }

    search = assert_success(client.get("/communication/api/v1/notifications?search=failed", headers=auth_headers))
    assert [item["notification_id"] for item in search["notifications"]] == ["NOT-FAILED-001"]

    assert_success(client.get("/communication/api/v1/notifications?page=99", headers=auth_headers))["notifications"] == []


def test_invalid_notification_queries_use_standard_422(client, auth_headers):
    assert_error(client.get("/communication/api/v1/notifications?page=0", headers=auth_headers), 422, "COMMUNICATION_422")
    assert_error(client.get("/communication/api/v1/notifications?page_size=101", headers=auth_headers), 422, "COMMUNICATION_422")
    assert_error(client.get("/communication/api/v1/notifications?status=retrying", headers=auth_headers), 422, "COMMUNICATION_422")
    assert_error(client.get("/communication/api/v1/notifications?channel=pager", headers=auth_headers), 422, "COMMUNICATION_422")
    assert_error(
        client.get(
            "/communication/api/v1/notifications?created_after=2026-07-23T00:00:00Z&created_before=2026-07-22T00:00:00Z",
            headers=auth_headers,
        ),
        422,
        "COMMUNICATION_422",
    )


def test_get_notification_existing_missing_and_legacy_routes(client, auth_headers):
    delivered = assert_success(
        client.get("/communication/api/v1/notifications/NOT-EMAIL-DELIVERED", headers=auth_headers)
    )
    assert delivered["status"] == "DELIVERED"

    failed = assert_success(client.get("/communication/api/v1/notifications/NOT-FAILED-001", headers=auth_headers))
    assert failed["status"] == "FAILED"
    assert failed["failure_reason"] == "Simulated delivery failed"

    assert_error(
        client.get("/communication/api/v1/notifications/NOT-MISSING", headers=auth_headers),
        404,
        "COMMUNICATION_404",
    )

    legacy_created = client.post(
        "/notifications",
        json={
            "recipientType": "SPECIALIST",
            "recipientId": "SPEC-MAYA",
            "notificationType": "IN_APP",
            "message": "Legacy notification",
            "idempotencyKey": "NOT-LEGACY-001",
        },
        headers=auth_headers,
    )
    assert legacy_created.status_code == 200
    notification_id = legacy_created.json()["notificationId"]

    legacy_get = client.get(f"/notifications/{notification_id}", headers=auth_headers)
    assert legacy_get.status_code == 200
    assert legacy_get.json()["notificationId"] == notification_id

    legacy_list = client.get("/notifications", headers=auth_headers)
    assert legacy_list.status_code == 200
    assert any(item["notificationId"] == notification_id for item in legacy_list.json())


def test_simulation_load_state_replaces_assignments_and_notifications(client, auth_headers, admin_headers):
    payload = {
        "scenario_id": "scenario-test",
        "assignment_requests": [
            {
                "request_id": "ar-sim-001",
                "run_id": "run-sim",
                "incident_id": "inc-sim-001",
                "specialist_id": "spec-maya",
                "reservation_id": "res-sim-001",
                "message": "Simulation assignment request.",
                "status": "ACCEPTED",
                "idempotency_key": "ar-sim-001",
                "created_at": "2026-07-22T09:00:00Z",
                "expires_at": "2026-07-22T10:00:00Z",
                "responded_at": "2026-07-22T09:05:00Z",
                "response_note": "Accepted.",
                "response_reason": "Accepted.",
                "updated_at": "2026-07-22T09:05:00Z",
            }
        ],
        "notifications": [
            {
                "notification_id": "not-sim-001",
                "recipient": "maya.sen@example.test",
                "channel": "EMAIL",
                "subject": "Simulation notification",
                "message": "Simulation notification delivered.",
                "status": "DELIVERED",
                "idempotency_key": "not-sim-001",
                "related_request_id": "ar-sim-001",
                "created_at": "2026-07-22T09:06:00Z",
                "attempted_at": "2026-07-22T09:06:00Z",
                "delivered_at": "2026-07-22T09:06:00Z",
                "attempt_count": 1,
                "updated_at": "2026-07-22T09:06:00Z",
            }
        ],
    }

    loaded = client.post("/admin/simulation/load-state", json=payload, headers=admin_headers)
    assert loaded.status_code == 200
    data = assert_success(loaded)
    assert data["assignment_request_count"] == 1
    assert data["notification_count"] == 1

    assignment = assert_success(
        client.get("/communication/api/v1/assignment-requests/AR-SIM-001", headers=auth_headers)
    )
    assert assignment["status"] == "ACCEPTED"

    notification = assert_success(client.get("/communication/api/v1/notifications/NOT-SIM-001", headers=auth_headers))
    assert notification["related_request_id"] == "AR-SIM-001"
