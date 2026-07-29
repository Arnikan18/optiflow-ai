import secrets

from fastapi import APIRouter, Depends, Header, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession
from starlette.concurrency import run_in_threadpool

from app.config.models import (
    DEFAULT_MODELS,
    PROVIDER_LABELS,
    SETTINGS_SCHEMA_VERSION,
    SUPPORTED_MODELS,
)
from app.config.settings import settings
from app.goals.providers import build_llm_provider
from app.llm_settings.schemas import (
    CredentialConnectionResult,
    DisconnectRequest,
    LLMConnectionResponse,
    LLMSettingsInput,
    LLMSettingsResponse,
    ModelCatalogResponse,
    ProviderCatalog,
)
from app.llm_settings.service import (
    LLMSettingsConfigurationError,
    llm_settings_service,
)
from app.main_dependencies import get_db


router = APIRouter(prefix="/api/v1/settings/llm", tags=["LLM settings"])


def require_admin_key(
    supplied_key: str | None = Header(default=None, alias="X-Admin-Key"),
) -> None:
    configured_key = settings.admin_api_key.strip()
    if not configured_key:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Secure settings changes are not configured on Core.",
        )
    if not supplied_key or not secrets.compare_digest(supplied_key, configured_key):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid Core admin key.",
        )


@router.get("/models", response_model=ModelCatalogResponse)
async def list_models() -> ModelCatalogResponse:
    return ModelCatalogResponse(
        version=SETTINGS_SCHEMA_VERSION,
        providers=[
            ProviderCatalog(
                id=provider,
                label=PROVIDER_LABELS[provider],
                default_model=DEFAULT_MODELS[provider],
                models=list(models),
            )
            for provider, models in SUPPORTED_MODELS.items()
        ],
    )


@router.get("", response_model=LLMSettingsResponse)
async def get_llm_settings() -> LLMSettingsResponse:
    return llm_settings_service.response()


async def test_connections(
    payload: LLMSettingsInput,
) -> LLMConnectionResponse:
    provider_name = payload.active_llm_provider
    if payload.mode != "ai_assisted" or provider_name is None:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="Connection testing requires AI-assisted mode.",
        )
    provider_settings = payload.providers[provider_name]
    results: list[CredentialConnectionResult] = []
    for credential in sorted(
        provider_settings.credentials,
        key=lambda item: item.priority,
    ):
        provider = build_llm_provider(
            provider_name,
            provider_settings.model_name,
            [credential.api_key.get_secret_value()],
        )
        try:
            response = await run_in_threadpool(
                provider.generate_text,
                "Reply with exactly: OPTIFLOW_CONNECTED",
                0.0,
            )
            connected = bool(response and response.strip())
            message = (
                "Provider accepted this credential."
                if connected
                else "Provider returned an empty response."
            )
        except Exception as error:
            connected = False
            status_code = getattr(error, "status_code", None)
            if status_code in {401, 403}:
                message = "Provider rejected this credential."
            elif status_code == 429:
                message = "Credential is valid but its current quota is exhausted."
            else:
                message = "Provider connection or model validation failed."
        results.append(
            CredentialConnectionResult(
                label=credential.label,
                priority=credential.priority,
                connected=connected,
                message=message,
            )
        )
    return LLMConnectionResponse(
        connected=all(result.connected for result in results),
        saved=False,
        provider=provider_name,
        model_name=provider_settings.model_name,
        credentials=results,
    )


@router.post("/test", response_model=LLMConnectionResponse)
async def test_llm_settings(
    payload: LLMSettingsInput,
    _: None = Depends(require_admin_key),
) -> LLMConnectionResponse:
    return await test_connections(payload)


@router.post("", response_model=LLMConnectionResponse)
async def save_llm_settings(
    payload: LLMSettingsInput,
    db: AsyncSession = Depends(get_db),
    _: None = Depends(require_admin_key),
) -> LLMConnectionResponse:
    if payload.mode == "rules_only":
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="Use the disconnect endpoint to enable rules-only mode.",
        )

    connection = await test_connections(payload)
    if not connection.connected:
        failed_labels = [
            result.label
            for result in connection.credentials
            if not result.connected
        ]
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=(
                "Provider settings were not saved because these credentials failed: "
                + ", ".join(failed_labels)
            ),
        )
    try:
        await llm_settings_service.save(db, payload)
    except LLMSettingsConfigurationError as error:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail=str(error),
        ) from error
    return connection.model_copy(update={"saved": True})


@router.post("/disconnect", response_model=LLMSettingsResponse)
async def disconnect_llm_settings(
    payload: DisconnectRequest,
    db: AsyncSession = Depends(get_db),
    _: None = Depends(require_admin_key),
) -> LLMSettingsResponse:
    try:
        runtime = await llm_settings_service.disconnect(db, payload.provider)
    except LLMSettingsConfigurationError as error:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail=str(error),
        ) from error
    return llm_settings_service.response(runtime)
