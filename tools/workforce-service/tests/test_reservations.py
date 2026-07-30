import asyncio

from sqlalchemy import select
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.ext.asyncio import AsyncSession

from tests.test_specialists import assert_error, assert_success, reservation_payload


def set_specialist_state(specialist_id: str, **updates):
    async def run_update():
        from app.database import session as db_session
        from app.database.models import Specialist

        async with db_session.async_session() as session:
            specialist = await session.get(Specialist, updates.pop("id", None)) if "id" in updates else None
            if specialist is None:
                result = await session.execute(select(Specialist).where(Specialist.specialist_id == specialist_id))
                specialist = result.scalar_one()
            for field, value in updates.items():
                setattr(specialist, field, value)
            await session.commit()

    asyncio.run(run_update())


def test_create_reservation_success_duplicate_and_capacity(client, auth_headers):
    created = assert_success(
        client.post("/workforce/api/v1/reservations", json=reservation_payload(), headers=auth_headers),
        201,
    )
    assert created["reservation_id"] == "RES-TEST-001"
    assert created["specialist_id"] == "SPEC-DANIEL"
    assert created["incident_id"] == "INC-TEST-001"
    assert created["run_id"] is None
    assert created["idempotency_key"] is None
    assert created["status"] == "TENTATIVE"
    assert created["confirmed_at"] is None

    assert_error(
        client.post("/workforce/api/v1/reservations", json=reservation_payload(), headers=auth_headers),
        409,
        "WORKFORCE_409",
    )
    assert_error(
        client.post(
            "/workforce/api/v1/reservations",
            json=reservation_payload(reservation_id="RES-TEST-002"),
            headers=auth_headers,
        ),
        409,
        "WORKFORCE_409",
    )
    assert_error(
        client.post(
            "/workforce/api/v1/reservations",
            json=reservation_payload(reservation_id="RES-MISSING", specialist_id="SPEC-MISSING"),
            headers=auth_headers,
        ),
        404,
        "WORKFORCE_404",
    )
    assert_error(
        client.post(
            "/workforce/api/v1/reservations",
            json=reservation_payload(reservation_id="RES-INACTIVE", specialist_id="SPEC-KAI"),
            headers=auth_headers,
        ),
        409,
        "WORKFORCE_409",
    )
    assert_error(
        client.post(
            "/workforce/api/v1/reservations",
            json=reservation_payload(reservation_id="RES-UNAVAILABLE", specialist_id="SPEC-PRIYA"),
            headers=auth_headers,
        ),
        409,
        "WORKFORCE_409",
    )
    assert_error(
        client.post(
            "/workforce/api/v1/reservations",
            json=reservation_payload(reservation_id="RES-FULL", specialist_id="SPEC-NIMAL"),
            headers=auth_headers,
        ),
        409,
        "WORKFORCE_409",
    )


def test_create_reservation_idempotency_replay_and_payload_mismatch(client, auth_headers):
    payload = reservation_payload(
        reservation_id="RES-IDEM-001",
        incident_id="INC-IDEM-001",
        run_id="RUN-IDEM-001",
        idempotency_key="res-idem-001",
    )
    created = assert_success(
        client.post("/workforce/api/v1/reservations", json=payload, headers=auth_headers),
        201,
    )
    replay = assert_success(
        client.post("/workforce/api/v1/reservations", json=payload, headers=auth_headers),
        200,
    )
    assert replay == created
    assert replay["run_id"] == "RUN-IDEM-001"
    assert replay["idempotency_key"] == "res-idem-001"

    mismatch = dict(payload)
    mismatch["incident_id"] = "INC-IDEM-CHANGED"
    assert_error(
        client.post("/workforce/api/v1/reservations", json=mismatch, headers=auth_headers),
        409,
        "WORKFORCE_409",
    )


def test_reservation_allows_new_after_cancel_and_after_expiry(client, auth_headers):
    created = assert_success(
        client.post(
            "/workforce/api/v1/reservations",
            json=reservation_payload(reservation_id="RES-CANCEL-001", incident_id="INC-CANCEL-NEW"),
            headers=auth_headers,
        ),
        201,
    )
    assert_success(client.delete(f"/workforce/api/v1/reservations/{created['reservation_id']}", headers=auth_headers))
    replacement = assert_success(
        client.post(
            "/workforce/api/v1/reservations",
            json=reservation_payload(reservation_id="RES-CANCEL-002", incident_id="INC-CANCEL-NEW"),
            headers=auth_headers,
        ),
        201,
    )
    assert replacement["reservation_id"] == "RES-CANCEL-002"
    assert_success(client.delete(f"/workforce/api/v1/reservations/{replacement['reservation_id']}", headers=auth_headers))

    after_expiry = assert_success(
        client.post(
            "/workforce/api/v1/reservations",
            json=reservation_payload(reservation_id="RES-AFTER-EXPIRY", incident_id="INC-EXPIRED-001"),
            headers=auth_headers,
        ),
        201,
    )
    assert after_expiry["status"] == "TENTATIVE"


def test_get_reservation_existing_missing_and_expired(client, auth_headers):
    pending = assert_success(client.get("/workforce/api/v1/reservations/RES-MAYA-TENTATIVE", headers=auth_headers))
    assert pending["status"] == "TENTATIVE"

    expired = assert_success(client.get("/workforce/api/v1/reservations/RES-DANIEL-EXPIRED", headers=auth_headers))
    assert expired["status"] == "EXPIRED"

    assert_error(
        client.get("/workforce/api/v1/reservations/RES-MISSING", headers=auth_headers),
        404,
        "WORKFORCE_404",
    )


def test_confirm_reservation_idempotent_and_workload_increment(client, auth_headers):
    before = assert_success(client.get("/workforce/api/v1/specialists/SPEC-DANIEL", headers=auth_headers))
    created = assert_success(
        client.post(
            "/workforce/api/v1/reservations",
            json=reservation_payload(reservation_id="RES-CONFIRM-001", incident_id="INC-CONFIRM-001"),
            headers=auth_headers,
        ),
        201,
    )
    confirmed = assert_success(
        client.patch(f"/workforce/api/v1/reservations/{created['reservation_id']}/confirm", headers=auth_headers)
    )
    assert confirmed["status"] == "CONFIRMED"
    assert confirmed["confirmed_at"] is not None

    after = assert_success(client.get("/workforce/api/v1/specialists/SPEC-DANIEL", headers=auth_headers))
    assert after["current_workload"] == before["current_workload"] + 1

    repeated = assert_success(
        client.patch(f"/workforce/api/v1/reservations/{created['reservation_id']}/confirm", headers=auth_headers)
    )
    assert repeated["status"] == "CONFIRMED"
    after_repeat = assert_success(client.get("/workforce/api/v1/specialists/SPEC-DANIEL", headers=auth_headers))
    assert after_repeat["current_workload"] == after["current_workload"]


def verification_payload(**overrides):
    payload = {
        "reservation_id": "RES-VERIFY-OK",
        "expected_run_id": "RUN-VERIFY-001",
        "expected_incident_id": "INC-VERIFY-001",
        "expected_specialist_id": "SPEC-DANIEL",
        "expected_status": "CONFIRMED",
    }
    payload.update(overrides)
    return payload


def test_verify_confirmed_reservation_and_mismatches(client, auth_headers):
    created = assert_success(
        client.post(
            "/workforce/api/v1/reservations",
            json=reservation_payload(
                reservation_id="RES-VERIFY-OK",
                incident_id="INC-VERIFY-001",
                run_id="RUN-VERIFY-001",
            ),
            headers=auth_headers,
        ),
        201,
    )
    assert_success(client.patch(f"/workforce/api/v1/reservations/{created['reservation_id']}/confirm", headers=auth_headers))

    verified = assert_success(
        client.post("/workforce/api/v1/reservations/verify", json=verification_payload(), headers=auth_headers)
    )
    assert verified["verified"] is True
    assert verified["result"] == "verified"
    assert verified["current_status"] == "CONFIRMED"
    assert verified["failed_checks"] == []

    wrong_specialist = assert_success(
        client.post(
            "/workforce/api/v1/reservations/verify",
            json=verification_payload(expected_specialist_id="SPEC-MAYA"),
            headers=auth_headers,
        )
    )
    assert wrong_specialist["verified"] is False
    assert wrong_specialist["result"] == "inconsistent"
    assert "specialist_id_mismatch" in wrong_specialist["failed_checks"]

    wrong_incident = assert_success(
        client.post(
            "/workforce/api/v1/reservations/verify",
            json=verification_payload(expected_incident_id="INC-WRONG"),
            headers=auth_headers,
        )
    )
    assert wrong_incident["verified"] is False
    assert "incident_id_mismatch" in wrong_incident["failed_checks"]


def test_verify_tentative_cancelled_expired_and_unknown_reservations(client, auth_headers):
    tentative = assert_success(
        client.post(
            "/workforce/api/v1/reservations",
            json=reservation_payload(
                reservation_id="RES-VERIFY-PENDING",
                incident_id="INC-VERIFY-PENDING",
                specialist_id="SPEC-MAYA",
                run_id="RUN-VERIFY-PENDING",
            ),
            headers=auth_headers,
        ),
        201,
    )
    pending = assert_success(
        client.post(
            "/workforce/api/v1/reservations/verify",
            json=verification_payload(
                reservation_id=tentative["reservation_id"],
                expected_run_id="RUN-VERIFY-PENDING",
                expected_incident_id="INC-VERIFY-PENDING",
                expected_specialist_id="SPEC-MAYA",
            ),
            headers=auth_headers,
        )
    )
    assert pending["verified"] is False
    assert pending["result"] == "pending"
    assert "status_not_confirmed" in pending["failed_checks"]

    cancelled_seed = assert_success(client.get("/workforce/api/v1/reservations/RES-PRIYA-CANCELLED", headers=auth_headers))
    cancelled = assert_success(
        client.post(
            "/workforce/api/v1/reservations/verify",
            json=verification_payload(
                reservation_id=cancelled_seed["reservation_id"],
                expected_run_id="RUN-CANCELLED",
                expected_incident_id=cancelled_seed["incident_id"],
                expected_specialist_id=cancelled_seed["specialist_id"],
            ),
            headers=auth_headers,
        )
    )
    assert cancelled["verified"] is False
    assert cancelled["result"] == "cancelled"
    assert "reservation_cancelled" in cancelled["failed_checks"]

    expired = assert_success(
        client.post(
            "/workforce/api/v1/reservations/verify",
            json=verification_payload(
                reservation_id="RES-DANIEL-EXPIRED",
                expected_run_id="RUN-EXPIRED",
                expected_incident_id="INC-EXPIRED-001",
                expected_specialist_id="SPEC-DANIEL",
            ),
            headers=auth_headers,
        )
    )
    assert expired["verified"] is False
    assert expired["result"] == "expired"
    assert "reservation_expired" in expired["failed_checks"]

    unknown = assert_success(
        client.post(
            "/workforce/api/v1/reservations/verify",
            json=verification_payload(reservation_id="RES-UNKNOWN"),
            headers=auth_headers,
        )
    )
    assert unknown["verified"] is False
    assert unknown["result"] == "not_found"
    assert unknown["actual_values"] is None


def test_confirm_rejects_cancelled_expired_inactive_and_capacity(client, auth_headers):
    assert_error(
        client.patch("/workforce/api/v1/reservations/RES-PRIYA-CANCELLED/confirm", headers=auth_headers),
        409,
        "WORKFORCE_409",
    )
    assert_error(
        client.patch("/workforce/api/v1/reservations/RES-DANIEL-EXPIRED/confirm", headers=auth_headers),
        409,
        "WORKFORCE_409",
    )

    created = assert_success(
        client.post(
            "/workforce/api/v1/reservations",
            json=reservation_payload(reservation_id="RES-INACTIVE-CONFIRM", specialist_id="SPEC-MAYA", incident_id="INC-INACTIVE-CONFIRM"),
            headers=auth_headers,
        ),
        201,
    )
    set_specialist_state("SPEC-MAYA", active=False)
    assert_error(
        client.patch(f"/workforce/api/v1/reservations/{created['reservation_id']}/confirm", headers=auth_headers),
        409,
        "WORKFORCE_409",
    )

    set_specialist_state("SPEC-MAYA", active=True, current_workload=2)
    assert_error(
        client.patch(f"/workforce/api/v1/reservations/{created['reservation_id']}/confirm", headers=auth_headers),
        409,
        "WORKFORCE_409",
    )


def test_cancel_pending_release_confirmed_repeat_and_missing(client, auth_headers):
    pending = assert_success(
        client.post(
            "/workforce/api/v1/reservations",
            json=reservation_payload(reservation_id="RES-CANCEL-PENDING", incident_id="INC-CANCEL-PENDING"),
            headers=auth_headers,
        ),
        201,
    )
    cancelled = assert_success(
        client.delete(
            f"/workforce/api/v1/reservations/{pending['reservation_id']}?cancellation_reason=No%20longer%20needed",
            headers=auth_headers,
        )
    )
    assert cancelled["status"] == "CANCELLED"
    assert cancelled["cancellation_reason"] == "No longer needed"
    repeated = assert_success(
        client.delete(f"/workforce/api/v1/reservations/{pending['reservation_id']}", headers=auth_headers)
    )
    assert repeated["status"] == "CANCELLED"

    before = assert_success(client.get("/workforce/api/v1/specialists/SPEC-DANIEL", headers=auth_headers))
    released = assert_success(client.delete("/workforce/api/v1/reservations/RES-DANIEL-CONFIRMED", headers=auth_headers))
    assert released["status"] == "CANCELLED"
    after = assert_success(client.get("/workforce/api/v1/specialists/SPEC-DANIEL", headers=auth_headers))
    assert after["current_workload"] == max(before["current_workload"] - 1, 0)

    expired = assert_success(client.delete("/workforce/api/v1/reservations/RES-DANIEL-EXPIRED", headers=auth_headers))
    assert expired["status"] == "EXPIRED"
    assert_error(client.delete("/workforce/api/v1/reservations/RES-MISSING", headers=auth_headers), 404, "WORKFORCE_404")


def test_reservation_validation_and_auth(client, auth_headers):
    assert_error(client.get("/workforce/api/v1/specialists"), 401, "WORKFORCE_401")
    assert_error(client.get("/specialists"), 401, "WORKFORCE_401")
    for overrides in [
        {"reservation_id": "   "},
        {"specialist_id": "   "},
        {"incident_id": "   "},
        {"expires_in_seconds": 29},
        {"expires_in_seconds": 3601},
        {"created_at": "2099-01-01T00:00:00Z"},
    ]:
        assert_error(
            client.post("/workforce/api/v1/reservations", json=reservation_payload(**overrides), headers=auth_headers),
            422,
            "WORKFORCE_422",
        )


def test_legacy_reservation_routes(client, auth_headers):
    created = client.post(
        "/reservations/tentative",
        json={"specialistId": "SPEC-DANIEL", "escalationId": "INC-LEGACY-001", "idempotencyKey": "RES-LEGACY-001"},
        headers=auth_headers,
    )
    assert created.status_code == 200
    reservation_id = created.json()["reservationId"]

    confirmed = client.post(f"/reservations/{reservation_id}/confirm", headers=auth_headers)
    assert confirmed.status_code == 200
    assert confirmed.json()["status"] == "CONFIRMED"

    cancelled = client.delete(f"/reservations/{reservation_id}", headers=auth_headers)
    assert cancelled.status_code == 200


def test_admin_reset_auth_determinism_and_missing_config(client, admin_headers, auth_headers, monkeypatch):
    assert_error(client.post("/admin/reset"), 401, "WORKFORCE_401")
    assert_error(client.post("/admin/reset", headers={"X-Admin-Key": "wrong"}), 401, "WORKFORCE_401")

    assert_success(
        client.post(
            "/workforce/api/v1/reservations",
            json=reservation_payload(reservation_id="RES-RESET-001", incident_id="INC-RESET-001"),
            headers=auth_headers,
        ),
        201,
    )
    reset = assert_success(client.post("/admin/reset", headers=admin_headers))
    assert reset == {"specialist_count": 8, "reservation_count": 8}
    repeated = assert_success(client.post("/admin/reset", headers=admin_headers))
    assert repeated == {"specialist_count": 8, "reservation_count": 8}
    assert_error(
        client.get("/workforce/api/v1/reservations/RES-RESET-001", headers=auth_headers),
        404,
        "WORKFORCE_404",
    )

    from app.config import get_settings

    monkeypatch.delenv("ADMIN_API_KEY", raising=False)
    get_settings.cache_clear()
    assert_error(client.post("/admin/reset", headers=admin_headers), 503, "WORKFORCE_503")
    monkeypatch.setenv("ADMIN_API_KEY", "test-admin-key")
    get_settings.cache_clear()


def test_failed_create_and_confirm_roll_back(client, auth_headers, monkeypatch):
    async def fail_commit(self):
        raise SQLAlchemyError("commit failed at C:/secret/workforce.db")

    with monkeypatch.context() as patch:
        patch.setattr(AsyncSession, "commit", fail_commit)
        response = client.post(
            "/workforce/api/v1/reservations",
            json=reservation_payload(reservation_id="RES-ROLLBACK-001", incident_id="INC-ROLLBACK-001"),
            headers=auth_headers,
        )

    assert_error(response, 503, "WORKFORCE_503")
    assert "secret" not in response.text
    assert_error(
        client.get("/workforce/api/v1/reservations/RES-ROLLBACK-001", headers=auth_headers),
        404,
        "WORKFORCE_404",
    )
