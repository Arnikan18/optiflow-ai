import asyncio

from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.ext.asyncio import AsyncSession

from app.database.models import Incident
from app.database.seed import build_seed_incidents

from tests.test_incidents import assert_error, assert_success, incident_payload


def test_tool_token_required_for_incident_and_legacy_routes(client):
    assert_error(client.get("/incident/api/v1/incidents"), 401, "INCIDENT_401")
    assert_error(client.get("/escalations/active"), 401, "INCIDENT_401")


def test_invalid_list_queries_use_standard_error_shape(client, auth_headers):
    assert_error(client.get("/incident/api/v1/incidents?page=0", headers=auth_headers), 422, "INCIDENT_422")
    assert_error(client.get("/incident/api/v1/incidents?page_size=101", headers=auth_headers), 422, "INCIDENT_422")
    assert_error(client.get("/incident/api/v1/incidents?priority=P1", headers=auth_headers), 422, "INCIDENT_422")
    assert_error(client.get("/incident/api/v1/incidents?status=ASSIGNED", headers=auth_headers), 422, "INCIDENT_422")
    assert_error(
        client.get(
            "/incident/api/v1/incidents?sla_after=2099-12-31T00:00:00Z&sla_before=2099-01-01T00:00:00Z",
            headers=auth_headers,
        ),
        422,
        "INCIDENT_422",
    )
    assert_error(
        client.get(
            "/incident/api/v1/incidents?unassigned=true&assigned_specialist_id=SPEC-MAYA",
            headers=auth_headers,
        ),
        422,
        "INCIDENT_422",
    )


def test_create_validation_edge_cases(client, auth_headers):
    for overrides in [
        {"incident_id": "   "},
        {"customer_id": "   "},
        {"title": "   "},
        {"description": "   "},
        {"priority": "urgent"},
        {"sla_deadline": "not-a-date"},
        {"sla_deadline": "2099-08-01T10:00:00"},
        {"status": "CLOSED"},
        {"created_at": "2099-01-01T00:00:00Z"},
    ]:
        assert_error(
            client.post("/incident/api/v1/incidents", json=incident_payload(**overrides), headers=auth_headers),
            422,
            "INCIDENT_422",
        )

    unicode_incident = assert_success(
        client.post(
            "/incident/api/v1/incidents",
            json=incident_payload(
                incident_id="INC-UNICODE-001",
                title="Unicode title -  කාර්යය",
                description="Unicode description - සේවා අවදානම",
            ),
            headers=auth_headers,
        ),
        201,
    )
    assert unicode_incident["incident_id"] == "INC-UNICODE-001"


def test_status_update_validation_missing_and_not_mass_assignable(client, auth_headers):
    assert_error(
        client.patch(
            "/incident/api/v1/incidents/INC-GREEN-001/status",
            json={"status": "ASSIGNED"},
            headers=auth_headers,
        ),
        422,
        "INCIDENT_422",
    )
    assert_error(
        client.patch(
            "/incident/api/v1/incidents/INC-MISSING/status",
            json={"status": "IN_PROGRESS"},
            headers=auth_headers,
        ),
        404,
        "INCIDENT_404",
    )
    assert_error(
        client.patch(
            "/incident/api/v1/incidents/INC-GREEN-001/status",
            json={"status": "IN_PROGRESS", "assigned_specialist_id": "SPEC-MAYA"},
            headers=auth_headers,
        ),
        422,
        "INCIDENT_422",
    )


def test_assignment_validation(client, auth_headers):
    assert_error(
        client.post(
            "/incident/api/v1/incidents/INC-GREEN-001/assign",
            json={"specialist_id": "   "},
            headers=auth_headers,
        ),
        422,
        "INCIDENT_422",
    )
    assert_error(
        client.post(
            "/incident/api/v1/incidents/INC-GREEN-001/assign",
            json={"specialist_id": "SPEC-MAYA", "status": "IN_PROGRESS"},
            headers=auth_headers,
        ),
        422,
        "INCIDENT_422",
    )


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
        from app.services.incident_service import seed_incidents_if_empty

        get_settings.cache_clear()
        await db_session.configure_database(database_url)
        async with db_session.engine.begin() as conn:
            await conn.run_sync(Base.metadata.create_all)

        async with db_session.async_session() as session:
            assert await seed_incidents_if_empty(session) == 5
        async with db_session.async_session() as session:
            assert await seed_incidents_if_empty(session) == 0
        async with db_session.async_session() as session:
            custom = build_seed_incidents()[0]
            custom.incident_id = "INC-CUSTOM-001"
            session.add(custom)
            await session.commit()
        async with db_session.async_session() as session:
            assert await seed_incidents_if_empty(session) == 0
            result = await session.get(Incident, 6)
            assert result.incident_id == "INC-CUSTOM-001"
        await db_session.engine.dispose()
        get_settings.cache_clear()

    asyncio.run(run_check())


def test_readiness_failure_is_controlled(client, monkeypatch):
    from app.database import session as db_session

    async def fail_execute(*args, **kwargs):
        raise SQLAlchemyError("database exploded")

    class BrokenSession:
        async def __aenter__(self):
            return self

        async def __aexit__(self, exc_type, exc, tb):
            return False

        async def execute(self, *args, **kwargs):
            return await fail_execute(*args, **kwargs)

    monkeypatch.setattr(db_session, "async_session", lambda: BrokenSession())
    response = client.get("/readiness")
    assert_error(response, 503, "INCIDENT_503")
    assert "database exploded" not in response.text


def test_failed_create_commit_rolls_back(client, auth_headers, monkeypatch):
    async def fail_commit(self):
        raise SQLAlchemyError("commit failed with internal path C:/secret/incident.db")

    with monkeypatch.context() as patch:
        patch.setattr(AsyncSession, "commit", fail_commit)
        response = client.post(
            "/incident/api/v1/incidents",
            json=incident_payload(incident_id="INC-ROLLBACK-001"),
            headers=auth_headers,
        )

    assert_error(response, 503, "INCIDENT_503")
    assert "secret" not in response.text
    assert_error(client.get("/incident/api/v1/incidents/INC-ROLLBACK-001", headers=auth_headers), 404, "INCIDENT_404")


def test_failed_reset_rolls_back(client, admin_headers, monkeypatch, auth_headers):
    async def fail_commit(self):
        raise SQLAlchemyError("reset failed")

    before = assert_success(client.get("/incident/api/v1/incidents", headers=auth_headers))
    with monkeypatch.context() as patch:
        patch.setattr(AsyncSession, "commit", fail_commit)
        response = client.post("/admin/reset", headers=admin_headers)

    assert_error(response, 503, "INCIDENT_503")
    after = assert_success(client.get("/incident/api/v1/incidents", headers=auth_headers))
    assert after["total_items"] == before["total_items"]
