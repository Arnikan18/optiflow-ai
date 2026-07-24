import asyncio
import sys
from pathlib import Path

import pytest
from fastapi.testclient import TestClient


SERVICE_ROOT = Path(__file__).resolve().parents[1]
REPO_ROOT = SERVICE_ROOT.parent.parent
SHARED_ROOT = REPO_ROOT / "shared" / "python"
for path in (SERVICE_ROOT, SHARED_ROOT):
    if str(path) not in sys.path:
        sys.path.insert(0, str(path))

TOOL_TOKEN = "test-tool-token"
ADMIN_KEY = "test-admin-key"


@pytest.fixture
def auth_headers() -> dict[str, str]:
    return {"X-Tool-Token": TOOL_TOKEN}


@pytest.fixture
def admin_headers() -> dict[str, str]:
    return {"X-Admin-Key": ADMIN_KEY}


@pytest.fixture
def client(tmp_path, monkeypatch):
    db_path = tmp_path / "communication-test.db"
    database_url = f"sqlite:///{db_path.as_posix()}"

    monkeypatch.setenv("DATABASE_URL", database_url)
    monkeypatch.setenv("TOOL_SHARED_TOKEN", TOOL_TOKEN)
    monkeypatch.setenv("ADMIN_API_KEY", ADMIN_KEY)
    monkeypatch.setenv("SERVICE_NAME", "communication-service")
    monkeypatch.setenv("SERVICE_PORT", "8104")
    monkeypatch.setenv("ASSIGNMENT_REQUEST_TTL_SECONDS", "900")
    monkeypatch.setenv("SIMULATED_DELIVERY_MODE", "recipient_rule")

    from app.config import get_settings
    from app.database import session as db_session
    from app.main import create_app

    get_settings.cache_clear()
    asyncio.run(db_session.configure_database(database_url))

    with TestClient(create_app()) as test_client:
        yield test_client

    asyncio.run(db_session.engine.dispose())
    get_settings.cache_clear()
