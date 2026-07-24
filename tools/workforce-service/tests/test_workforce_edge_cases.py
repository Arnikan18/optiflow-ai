import asyncio

from sqlalchemy import delete, select
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.ext.asyncio import AsyncSession

from app.database.models import Reservation, Specialist
from app.database.seed import build_seed_specialists
from tests.test_specialists import assert_error, assert_success, reservation_payload


def test_empty_database_specialist_list(tmp_path, monkeypatch):
    db_path = tmp_path / "empty-workforce.db"
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
        data = assert_success(client.get("/workforce/api/v1/specialists", headers={"X-Tool-Token": "test-tool-token"}))
        assert data["total_items"] == 0
        assert data["specialists"] == []


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
        from app.database.seed import seed_workforce_if_empty

        get_settings.cache_clear()
        await db_session.configure_database(database_url)
        async with db_session.engine.begin() as conn:
            await conn.run_sync(Base.metadata.create_all)

        async with db_session.async_session() as session:
            assert await seed_workforce_if_empty(session) == {"specialist_count": 5, "reservation_count": 5}
        async with db_session.async_session() as session:
            assert await seed_workforce_if_empty(session) == {"specialist_count": 0, "reservation_count": 0}
        async with db_session.async_session() as session:
            custom = build_seed_specialists()[0]
            custom.specialist_id = "SPEC-CUSTOM"
            custom.email = "custom@example.test"
            custom.skills = []
            session.add(custom)
            await session.commit()
        async with db_session.async_session() as session:
            assert await seed_workforce_if_empty(session) == {"specialist_count": 0, "reservation_count": 0}
            result = await session.execute(select(Specialist).where(Specialist.specialist_id == "SPEC-CUSTOM"))
            assert result.scalar_one().email == "custom@example.test"
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
    assert_error(response, 503, "WORKFORCE_503")
    assert "sqlite" not in response.text


def test_reset_failure_rolls_back(client, admin_headers, auth_headers, monkeypatch):
    before = assert_success(client.get("/workforce/api/v1/specialists", headers=auth_headers))

    async def fail_commit(self):
        raise SQLAlchemyError("reset failed")

    with monkeypatch.context() as patch:
        patch.setattr(AsyncSession, "commit", fail_commit)
        response = client.post("/admin/reset", headers=admin_headers)

    assert_error(response, 503, "WORKFORCE_503")
    after = assert_success(client.get("/workforce/api/v1/specialists", headers=auth_headers))
    assert after["total_items"] == before["total_items"]


def test_expired_pending_does_not_consume_capacity_after_cleanup(client, auth_headers):
    before = assert_success(client.get("/workforce/api/v1/specialists/SPEC-DANIEL", headers=auth_headers))
    assert before["effective_workload"] == 1

    expired = assert_success(client.get("/workforce/api/v1/reservations/RES-DANIEL-EXPIRED", headers=auth_headers))
    assert expired["status"] == "EXPIRED"

    after = assert_success(client.get("/workforce/api/v1/specialists/SPEC-DANIEL", headers=auth_headers))
    assert after["effective_workload"] == 1


def test_duplicate_reservation_conflict_is_controlled(client, auth_headers):
    first = assert_success(
        client.post(
            "/workforce/api/v1/reservations",
            json=reservation_payload(reservation_id="RES-DUP-A", incident_id="INC-DUP-A"),
            headers=auth_headers,
        ),
        201,
    )
    assert first["status"] == "PENDING"
    assert_error(
        client.post(
            "/workforce/api/v1/reservations",
            json=reservation_payload(reservation_id="RES-DUP-A", incident_id="INC-DUP-B"),
            headers=auth_headers,
        ),
        409,
        "WORKFORCE_409",
    )


def test_cancelled_reservation_does_not_reduce_capacity(client, auth_headers):
    before = assert_success(client.get("/workforce/api/v1/specialists/SPEC-PRIYA", headers=auth_headers))
    assert before["effective_workload"] == 0
    cancelled = assert_success(client.get("/workforce/api/v1/reservations/RES-PRIYA-CANCELLED", headers=auth_headers))
    assert cancelled["status"] == "CANCELLED"
    after = assert_success(client.get("/workforce/api/v1/specialists/SPEC-PRIYA", headers=auth_headers))
    assert after["effective_workload"] == 0


def test_foreign_rows_removed_in_reset_order(client, admin_headers):
    reset = assert_success(client.post("/admin/reset", headers=admin_headers))
    assert reset == {"specialist_count": 5, "reservation_count": 5}
