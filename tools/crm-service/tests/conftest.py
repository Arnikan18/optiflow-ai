import os
import sys
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

SERVICE_ROOT = Path(__file__).resolve().parents[1]
if str(SERVICE_ROOT) not in sys.path:
    sys.path.insert(0, str(SERVICE_ROOT))

TOOL_TOKEN = "test-tool-token"
ADMIN_KEY = "test-admin-key"


@pytest.fixture()
def client(tmp_path, monkeypatch):
    database_url = f"sqlite:///{tmp_path / 'crm_test.db'}"
    monkeypatch.setenv("DATABASE_URL", database_url)
    monkeypatch.setenv("TOOL_SHARED_TOKEN", TOOL_TOKEN)
    monkeypatch.setenv("ADMIN_API_KEY", ADMIN_KEY)
    monkeypatch.setenv("SERVICE_NAME", "crm-service")
    monkeypatch.setenv("SERVICE_PORT", "8101")

    from app.config import get_settings
    from app.database import session as database_session
    from app.database.base import Base
    from app.database.seed import seed_customers
    from app.main import create_app

    get_settings.cache_clear()
    database_session.configure_database(database_url)
    Base.metadata.drop_all(bind=database_session.engine)
    Base.metadata.create_all(bind=database_session.engine)

    db = database_session.SessionLocal()
    try:
        seed_customers(db)
    finally:
        db.close()

    app = create_app(initialize_on_startup=False)
    with TestClient(app) as test_client:
        yield test_client

    database_session.engine.dispose()
    get_settings.cache_clear()


@pytest.fixture()
def auth_headers():
    return {"X-Tool-Token": TOOL_TOKEN}


@pytest.fixture()
def admin_headers():
    return {"X-Admin-Key": ADMIN_KEY}
