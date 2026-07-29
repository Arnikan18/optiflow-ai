import base64
import hashlib
import json
import logging
from dataclasses import dataclass

from cryptography.fernet import Fernet, InvalidToken
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.config.models import DEFAULT_MODELS, SETTINGS_SCHEMA_VERSION, validate_model
from app.config.settings import Settings, settings
from app.database.models import SystemSetting
from app.llm_settings.schemas import (
    CredentialStatus,
    LLMSettingsInput,
    LLMSettingsResponse,
    ProviderStatus,
)


logger = logging.getLogger("core-api.llm-settings")
SETTING_KEY = "llm"
PLACEHOLDER_KEYS = {"change-me", "your-api-key-here", "your-groq-key-here"}


class LLMSettingsConfigurationError(RuntimeError):
    """Raised when secure settings cannot be persisted safely."""


@dataclass(frozen=True)
class RuntimeCredential:
    label: str
    api_key: str
    priority: int


@dataclass(frozen=True)
class RuntimeProvider:
    model_name: str
    credentials: tuple[RuntimeCredential, ...]


@dataclass(frozen=True)
class RuntimeLLMSettings:
    version: int
    mode: str
    active_llm_provider: str | None
    providers: dict[str, RuntimeProvider]
    source: str

    def provider_for(
        self,
        provider_name: str | None = None,
        model_name: str | None = None,
    ) -> tuple[str, RuntimeProvider] | None:
        selected_name = provider_name or self.active_llm_provider
        if self.mode != "ai_assisted" or not selected_name:
            return None
        selected = self.providers.get(selected_name)
        if selected is None or not selected.credentials:
            return None
        resolved_model = model_name or selected.model_name
        validate_model(selected_name, resolved_model)
        return (
            selected_name,
            RuntimeProvider(
                model_name=resolved_model,
                credentials=selected.credentials,
            ),
        )


class LLMSettingsService:
    """Owns encrypted persistence and the in-memory runtime settings snapshot."""

    def __init__(self, app_settings: Settings):
        self._app_settings = app_settings
        self._runtime = self._from_environment()

    def current(self) -> RuntimeLLMSettings:
        return self._runtime

    async def load(self, session: AsyncSession) -> RuntimeLLMSettings:
        result = await session.execute(
            select(SystemSetting).where(SystemSetting.setting_key == SETTING_KEY)
        )
        record = result.scalar_one_or_none()
        if record is None:
            self._runtime = self._from_environment()
            return self._runtime
        if record.schema_version != SETTINGS_SCHEMA_VERSION:
            logger.warning(
                "Unsupported stored LLM settings version %s; using environment fallback.",
                record.schema_version,
            )
            self._runtime = self._from_environment()
            return self._runtime
        try:
            decrypted = self._fernet().decrypt(record.encrypted_value.encode("utf-8"))
            payload = LLMSettingsInput.model_validate_json(decrypted)
            self._runtime = self._from_payload(payload, source="database")
        except (
            InvalidToken,
            LLMSettingsConfigurationError,
            ValueError,
            TypeError,
            json.JSONDecodeError,
        ):
            logger.exception(
                "Stored LLM settings could not be loaded; using environment fallback."
            )
            self._runtime = self._from_environment()
        return self._runtime

    async def save(
        self,
        session: AsyncSession,
        payload: LLMSettingsInput,
    ) -> RuntimeLLMSettings:
        runtime = self._from_payload(payload, source="database")
        encrypted = self._fernet().encrypt(
            self._serialize(runtime).encode("utf-8")
        ).decode("utf-8")

        result = await session.execute(
            select(SystemSetting).where(SystemSetting.setting_key == SETTING_KEY)
        )
        record = result.scalar_one_or_none()
        if record is None:
            session.add(
                SystemSetting(
                    setting_key=SETTING_KEY,
                    encrypted_value=encrypted,
                    schema_version=SETTINGS_SCHEMA_VERSION,
                )
            )
        else:
            record.encrypted_value = encrypted
            record.schema_version = SETTINGS_SCHEMA_VERSION

        await session.commit()
        self._runtime = runtime
        return runtime

    async def disconnect(
        self,
        session: AsyncSession,
        provider_name: str | None = None,
    ) -> RuntimeLLMSettings:
        providers = {
            name: provider
            for name, provider in self._runtime.providers.items()
            if provider_name is not None and name != provider_name
        }
        active = self._runtime.active_llm_provider
        if active not in providers:
            active = next(iter(providers), None)
        mode = "ai_assisted" if active else "rules_only"
        runtime = RuntimeLLMSettings(
            version=SETTINGS_SCHEMA_VERSION,
            mode=mode,
            active_llm_provider=active,
            providers=providers,
            source="database",
        )
        payload = LLMSettingsInput.model_validate_json(self._serialize(runtime))
        return await self.save(session, payload)

    def response(self, runtime: RuntimeLLMSettings | None = None) -> LLMSettingsResponse:
        selected = runtime or self._runtime
        return LLMSettingsResponse(
            version=selected.version,
            mode=selected.mode,
            active_llm_provider=selected.active_llm_provider,
            providers={
                name: ProviderStatus(
                    model_name=provider.model_name,
                    credentials=[
                        CredentialStatus(
                            label=credential.label,
                            masked_key=self._mask(credential.api_key),
                            priority=credential.priority,
                        )
                        for credential in provider.credentials
                    ],
                )
                for name, provider in selected.providers.items()
            },
            source=selected.source,
        )

    def _from_environment(self) -> RuntimeLLMSettings:
        providers: dict[str, RuntimeProvider] = {}
        gemini_key = self._usable_key(self._app_settings.gemini_api_key)
        if gemini_key:
            gemini_model = self._app_settings.gemini_model or DEFAULT_MODELS["gemini"]
            validate_model("gemini", gemini_model)
            providers["gemini"] = RuntimeProvider(
                model_name=gemini_model,
                credentials=(RuntimeCredential("Environment", gemini_key, 0),),
            )

        groq_key = self._usable_key(self._app_settings.groq_api_key)
        if groq_key:
            groq_model = self._app_settings.groq_model or DEFAULT_MODELS["groq"]
            validate_model("groq", groq_model)
            providers["groq"] = RuntimeProvider(
                model_name=groq_model,
                credentials=(RuntimeCredential("Environment", groq_key, 0),),
            )

        requested = (self._app_settings.llm_provider or "").strip().lower()
        active = requested if requested in providers else next(iter(providers), None)
        return RuntimeLLMSettings(
            version=SETTINGS_SCHEMA_VERSION,
            mode="ai_assisted" if active else "rules_only",
            active_llm_provider=active,
            providers=providers,
            source="environment" if active else "rules_only",
        )

    @staticmethod
    def _from_payload(
        payload: LLMSettingsInput,
        source: str,
    ) -> RuntimeLLMSettings:
        providers = {
            name: RuntimeProvider(
                model_name=provider.model_name,
                credentials=tuple(
                    RuntimeCredential(
                        label=credential.label,
                        api_key=credential.api_key.get_secret_value(),
                        priority=credential.priority,
                    )
                    for credential in sorted(
                        provider.credentials,
                        key=lambda item: item.priority,
                    )
                ),
            )
            for name, provider in payload.providers.items()
        }
        active = payload.active_llm_provider if payload.mode == "ai_assisted" else None
        return RuntimeLLMSettings(
            version=payload.version,
            mode=payload.mode,
            active_llm_provider=active,
            providers=providers,
            source=source,
        )

    def _fernet(self) -> Fernet:
        secret = (
            self._app_settings.llm_settings_encryption_key.strip()
            or self._app_settings.admin_api_key.strip()
        )
        if not secret:
            raise LLMSettingsConfigurationError(
                "Set LLM_SETTINGS_ENCRYPTION_KEY before saving provider credentials."
            )
        derived_key = base64.urlsafe_b64encode(
            hashlib.sha256(secret.encode("utf-8")).digest()
        )
        return Fernet(derived_key)

    @staticmethod
    def _serialize(runtime: RuntimeLLMSettings) -> str:
        return json.dumps(
            {
                "version": runtime.version,
                "mode": runtime.mode,
                "active_llm_provider": runtime.active_llm_provider,
                "providers": {
                    name: {
                        "model_name": provider.model_name,
                        "credentials": [
                            {
                                "label": credential.label,
                                "api_key": credential.api_key,
                                "priority": credential.priority,
                            }
                            for credential in provider.credentials
                        ],
                    }
                    for name, provider in runtime.providers.items()
                },
            },
            separators=(",", ":"),
        )

    @staticmethod
    def _usable_key(value: str | None) -> str | None:
        normalized = (value or "").strip()
        if not normalized or normalized.lower() in PLACEHOLDER_KEYS:
            return None
        return normalized

    @staticmethod
    def _mask(value: str) -> str:
        suffix = value[-4:] if len(value) >= 4 else ""
        return f"••••••••{suffix}"


llm_settings_service = LLMSettingsService(settings)
