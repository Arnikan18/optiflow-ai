from fastapi import FastAPI
from fastapi.testclient import TestClient

from app.simulation.routes import router


app = FastAPI()
app.include_router(router)
client = TestClient(app)


def test_simulation_mutation_routes_require_demo_mode(monkeypatch):
    from app.config.settings import settings

    monkeypatch.setattr(settings, "demo_mode", False)
    monkeypatch.setattr(settings, "admin_api_key", "admin-test")

    response = client.post(
        "/api/v1/simulation/start",
        headers={"X-Admin-Key": "admin-test"},
        json={"scenario_id": "product_release_day"},
    )

    assert response.status_code == 403
    body = response.json()
    assert body["success"] is False
    assert body["errorCode"] == "SIMULATION_DEMO_MODE_DISABLED"
    assert "X-Request-ID" in response.headers


def test_simulation_mutation_routes_require_admin_key(monkeypatch):
    from app.config.settings import settings

    monkeypatch.setattr(settings, "demo_mode", True)
    monkeypatch.setattr(settings, "admin_api_key", "admin-test")

    response = client.post("/api/v1/simulation/pause", headers={"X-Admin-Key": "wrong"})

    assert response.status_code == 401
    body = response.json()
    assert body["success"] is False
    assert body["errorCode"] == "SIMULATION_ADMIN_UNAUTHORIZED"
    assert "X-Request-ID" in response.headers
