import asyncio
from datetime import datetime, timedelta, timezone

from sqlalchemy import select
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.ext.asyncio import AsyncSession

from app.database.models import AssignmentRequest
from tests.test_assignment_requests import assert_error, assert_success, assignment_payload
from tests.test_notifications import notification_payload


def test_empty_database_lists(tmp_path, monkeypatch):
    db_path = tmp_path / "empty-communication.db"
    database_url = f"sqlite:///{db_path.as_posix()}"
    monkeypatch.setenv("DATABASE_URL", database_url)
    monkeypatch.setenv("TOOL_SHARED_TOKEN", "test-tool-token")
    monkeypatch.setenv("ADMIN_API_KEY", "test-admin-key")
    monkeypatch.setenv("SEED_ON_STARTUP", "false")

    async def configure():
        from app.config import get_settings
        from app.database import session as db_session
        from app.database.base import Base

        get_settings.cache_clear()
        await db_session.configure_database(database_url)
        async with db_session.engine.begin() as conn:
            await conn.run_sync(Base.metadata.create_all)

    asyncio.run(configure())

    from app.main import create_app
    from fastapi.testclient import TestClient

    with TestClient(create_app(initialize_on_startup=False)) as client:
        headers = {"X-Tool-Token": "test-tool-token"}
        assignments = assert_success(client.get("/communication/api/v1/assignment-requests", headers=headers))
        notifications = assert_success(client.get("/communication/api/v1/notifications", headers=headers))
        assert assignments["total_items"] == 0
        assert notifications["total_items"] == 0


def test_seed_is_idempotent_and_does_not_overwrite_existing_data(tmp_path, monkeypatch):
    db_path = tmp_path / "seed-idempotent.db"
    database_url = f"sqlite:///{db_path.as_posix()}"
    monkeypatch.setenv("DATABASE_URL", database_url)
    monkeypatch.setenv("TOOL_SHARED_TOKEN", "test-tool-token")
    monkeypatch.setenv("ADMIN_API_KEY", "test-admin-key")

    async def run_check():
        from app.config import get_settings
        from app.database import session as db_session
        from app.database.base import Base
        from app.database.seed import seed_communication_if_empty

        get_settings.cache_clear()
        await db_session.configure_database(database_url)
        async with db_session.engine.begin() as conn:
            await conn.run_sync(Base.metadata.create_all)

        async with db_session.async_session() as session:
            assert await seed_communication_if_empty(session) == {
                "assignment_request_count": 5,
                "notification_count": 5,
            }
        async with db_session.async_session() as session:
            assert await seed_communication_if_empty(session) == {
                "assignment_request_count": 0,
                "notification_count": 0,
            }
        async with db_session.async_session() as session:
            custom = AssignmentRequest(
                request_id="AR-CUSTOM",
                incident_id="INC-CUSTOM",
                specialist_id="SPEC-CUSTOM",
                message="Custom user-created request",
                status="PENDING",
                created_at=datetime.now(timezone.utc),
                expires_at=datetime.now(timezone.utc) + timedelta(hours=1),
                updated_at=datetime.now(timezone.utc),
            )
            session.add(custom)
            await session.commit()
        async with db_session.async_session() as session:
            assert await seed_communication_if_empty(session) == {
                "assignment_request_count": 0,
                "notification_count": 0,
            }
            result = await session.execute(select(AssignmentRequest).where(AssignmentRequest.request_id == "AR-CUSTOM"))
            assert result.scalar_one().message == "Custom user-created request"
        await db_session.engine.dispose()
        get_settings.cache_clear()

    asyncio.run(run_check())


def test_readiness_failure_is_controlled(client, monkeypatch):
    from app.database import session as db_session

    class BrokenSession:
        async def __aenter__(self):
            return self

        async def __aexit__(self, exc_type, exc, tb):
            return False

        async def execute(self, *args, **kwargs):
            raise SQLAlchemyError("database exploded sqlite:///secret")

    monkeypatch.setattr(db_session, "async_session", lambda: BrokenSession())
    response = client.get("/readiness")
    assert_error(response, 503, "COMMUNICATION_503")
    assert "sqlite" not in response.text
    assert "secret" not in response.text


def test_admin_reset_auth_config_counts_and_rollback(client, admin_headers, auth_headers, monkeypatch):
    assert_error(client.post("/admin/reset"), 401, "COMMUNICATION_401")
    assert_error(client.post("/admin/reset", headers={"X-Admin-Key": "wrong"}), 401, "COMMUNICATION_401")

    reset = assert_success(client.post("/admin/reset", headers=admin_headers))
    assert reset == {"assignment_request_count": 5, "notification_count": 5}
    repeated = assert_success(client.post("/admin/reset", headers=admin_headers))
    assert repeated == reset

    from app.config import get_settings

    monkeypatch.delenv("ADMIN_API_KEY", raising=False)
    get_settings.cache_clear()
    assert_error(client.post("/admin/reset", headers=admin_headers), 503, "COMMUNICATION_503")
    monkeypatch.setenv("ADMIN_API_KEY", "test-admin-key")
    get_settings.cache_clear()

    before = assert_success(client.get("/communication/api/v1/assignment-requests", headers=auth_headers))

    async def fail_commit(self):
        raise SQLAlchemyError("reset failed at C:/secret/communication.db")

    with monkeypatch.context() as patch:
        patch.setattr(AsyncSession, "commit", fail_commit)
        response = client.post("/admin/reset", headers=admin_headers)

    assert_error(response, 503, "COMMUNICATION_503")
    after = assert_success(client.get("/communication/api/v1/assignment-requests", headers=auth_headers))
    assert after["total_items"] == before["total_items"]
    assert "secret" not in response.text


def test_assignment_create_failure_rolls_back(client, auth_headers, monkeypatch):
    async def fail_commit(self):
        raise SQLAlchemyError("commit failed at C:/secret/communication.db")

    with monkeypatch.context() as patch:
        patch.setattr(AsyncSession, "commit", fail_commit)
        response = client.post(
            "/communication/api/v1/assignment-requests",
            json=assignment_payload(request_id="AR-ROLLBACK-001", incident_id="INC-ROLLBACK-001"),
            headers=auth_headers,
        )

    assert_error(response, 503, "COMMUNICATION_503")
    assert "secret" not in response.text
    assert_error(
        client.get("/communication/api/v1/assignment-requests/AR-ROLLBACK-001", headers=auth_headers),
        404,
        "COMMUNICATION_404",
    )


def test_unexpected_delivery_exception_is_controlled(client, auth_headers, monkeypatch):
    from app.services import delivery_service

    def explode(**kwargs):
        raise RuntimeError("provider exploded at C:/secret/provider")

    monkeypatch.setattr(delivery_service, "simulate_delivery", explode)
    response = client.post(
        "/communication/api/v1/notifications",
        json=notification_payload(notification_id="NOT-EXPLODE-001", idempotency_key="notify-explode-001"),
        headers=auth_headers,
    )
    assert_error(response, 500, "COMMUNICATION_500")
    assert "secret" not in response.text
