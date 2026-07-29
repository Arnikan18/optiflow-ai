import pytest
from sqlalchemy import delete, select

from app.config.settings import Settings
from app.database.models import SystemSetting
from app.database.session import async_session
from app.llm_settings.schemas import LLMSettingsInput
from app.llm_settings.service import LLMSettingsService


def build_settings(**overrides) -> Settings:
    values = {
        "database_url": "sqlite+aiosqlite:///:memory:",
        "admin_api_key": "local-admin-key",
        "llm_settings_encryption_key": "unit-test-encryption-key",
        "gemini_api_key": "",
        "gemini_model": "gemini-3.6-flash",
        "groq_api_key": "",
        "groq_model": "llama-3.1-8b-instant",
    }
    values.update(overrides)
    return Settings(**values)


@pytest.mark.asyncio
async def test_save_encrypts_keys_and_loads_masked_runtime_settings():
    service = LLMSettingsService(build_settings())
    payload = LLMSettingsInput.model_validate(
        {
            "version": 1,
            "mode": "ai_assisted",
            "active_llm_provider": "gemini",
            "providers": {
                "gemini": {
                    "model_name": "gemini-3.6-flash",
                    "credentials": [
                        {
                            "label": "Primary",
                            "api_key": "gemini-secret-primary",
                            "priority": 0,
                        },
                        {
                            "label": "Backup",
                            "api_key": "gemini-secret-backup",
                            "priority": 1,
                        },
                    ],
                }
            },
        }
    )

    async with async_session() as session:
        await session.execute(delete(SystemSetting))
        await session.commit()
        saved = await service.save(session, payload)
        record = (
            await session.execute(
                select(SystemSetting).where(SystemSetting.setting_key == "llm")
            )
        ).scalar_one()

    assert saved.active_llm_provider == "gemini"
    assert "gemini-secret-primary" not in record.encrypted_value
    assert "gemini-secret-backup" not in record.encrypted_value
    response = service.response(saved)
    assert response.providers["gemini"].credentials[0].masked_key.endswith("mary")
    assert "gemini-secret-primary" not in response.model_dump_json()

    reloaded_service = LLMSettingsService(build_settings())
    async with async_session() as session:
        reloaded = await reloaded_service.load(session)

    provider_name, provider = reloaded.provider_for() or (None, None)
    assert provider_name == "gemini"
    assert provider is not None
    assert [item.api_key for item in provider.credentials] == [
        "gemini-secret-primary",
        "gemini-secret-backup",
    ]


@pytest.mark.asyncio
async def test_disconnect_removes_credentials_and_enables_rules_only_mode():
    service = LLMSettingsService(build_settings(groq_api_key="groq-live-key"))

    async with async_session() as session:
        await session.execute(delete(SystemSetting))
        await session.commit()
        disconnected = await service.disconnect(session)

    assert disconnected.mode == "rules_only"
    assert disconnected.active_llm_provider is None
    assert disconnected.providers == {}
    assert service.response().source == "database"


def test_environment_placeholders_do_not_enable_ai_mode():
    service = LLMSettingsService(
        build_settings(
            gemini_api_key="your-api-key-here",
            groq_api_key="your-groq-key-here",
        )
    )

    assert service.current().mode == "rules_only"
    assert service.current().providers == {}
