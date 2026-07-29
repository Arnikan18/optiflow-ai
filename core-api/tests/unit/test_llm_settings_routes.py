from unittest.mock import AsyncMock, MagicMock, patch

from fastapi import FastAPI
from fastapi.testclient import TestClient

from app.llm_settings.routes import router


app = FastAPI()
app.include_router(router)
client = TestClient(app)

PAYLOAD = {
    "version": 1,
    "mode": "ai_assisted",
    "active_llm_provider": "groq",
    "providers": {
        "groq": {
            "model_name": "llama-3.1-8b-instant",
            "credentials": [
                {
                    "label": "Primary",
                    "api_key": "groq-test-primary",
                    "priority": 0,
                }
            ],
        }
    },
}


def test_model_catalog_is_public_and_server_owned():
    response = client.get("/api/v1/settings/llm/models")

    assert response.status_code == 200
    providers = {item["id"]: item for item in response.json()["providers"]}
    assert "gemini-3.6-flash" in providers["gemini"]["models"]
    assert "llama-3.1-8b-instant" in providers["groq"]["models"]


def test_connection_test_rejects_wrong_admin_key():
    with patch("app.llm_settings.routes.settings.admin_api_key", "expected-key"):
        response = client.post(
            "/api/v1/settings/llm/test",
            headers={"X-Admin-Key": "wrong-key"},
            json=PAYLOAD,
        )

    assert response.status_code == 401
    assert response.json()["detail"] == "Invalid Core admin key."


def test_connection_test_calls_provider_without_saving():
    provider = MagicMock()
    provider.generate_text.return_value = "OPTIFLOW_CONNECTED"

    with (
        patch("app.llm_settings.routes.settings.admin_api_key", "expected-key"),
        patch(
            "app.llm_settings.routes.build_llm_provider",
            return_value=provider,
        ),
    ):
        response = client.post(
            "/api/v1/settings/llm/test",
            headers={"X-Admin-Key": "expected-key"},
            json=PAYLOAD,
        )

    assert response.status_code == 200
    assert response.json()["connected"] is True
    assert response.json()["saved"] is False
    provider.generate_text.assert_called_once()


def test_connect_provider_validates_then_saves_encrypted_configuration():
    provider = MagicMock()
    provider.generate_text.return_value = "OPTIFLOW_CONNECTED"

    with (
        patch("app.llm_settings.routes.settings.admin_api_key", "expected-key"),
        patch(
            "app.llm_settings.routes.build_llm_provider",
            return_value=provider,
        ),
        patch(
            "app.llm_settings.routes.llm_settings_service.save",
            new=AsyncMock(),
        ) as save,
    ):
        response = client.post(
            "/api/v1/settings/llm",
            headers={"X-Admin-Key": "expected-key"},
            json=PAYLOAD,
        )

    assert response.status_code == 200
    assert response.json()["connected"] is True
    assert response.json()["saved"] is True
    save.assert_awaited_once()
