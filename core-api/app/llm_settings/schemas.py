from typing import Literal

from pydantic import (
    BaseModel,
    ConfigDict,
    Field,
    SecretStr,
    field_validator,
    model_validator,
)

from app.config.models import SETTINGS_SCHEMA_VERSION, validate_model


ProviderName = Literal["gemini", "groq"]
DecisionEngineMode = Literal["rules_only", "ai_assisted"]


class CredentialInput(BaseModel):
    label: str = Field(min_length=1, max_length=80)
    api_key: SecretStr = Field(min_length=8, max_length=512)
    priority: int = Field(ge=0, le=9)

    @field_validator("label")
    @classmethod
    def normalize_label(cls, value: str) -> str:
        return value.strip()


class ProviderSettingsInput(BaseModel):
    model_config = ConfigDict(protected_namespaces=())

    model_name: str = Field(min_length=1, max_length=150)
    credentials: list[CredentialInput] = Field(min_length=1, max_length=3)

    @model_validator(mode="after")
    def validate_priorities(self) -> "ProviderSettingsInput":
        priorities = [credential.priority for credential in self.credentials]
        if len(priorities) != len(set(priorities)):
            raise ValueError("Credential priorities must be unique.")
        return self


class LLMSettingsInput(BaseModel):
    version: Literal[SETTINGS_SCHEMA_VERSION] = SETTINGS_SCHEMA_VERSION
    mode: DecisionEngineMode
    active_llm_provider: ProviderName | None = None
    providers: dict[ProviderName, ProviderSettingsInput] = Field(default_factory=dict)

    @model_validator(mode="after")
    def validate_provider_configuration(self) -> "LLMSettingsInput":
        if self.mode == "rules_only":
            return self
        if not self.active_llm_provider:
            raise ValueError("An active provider is required in AI-assisted mode.")
        provider_settings = self.providers.get(self.active_llm_provider)
        if provider_settings is None:
            raise ValueError("The active provider must be included in providers.")
        validate_model(self.active_llm_provider, provider_settings.model_name)
        return self


class CredentialStatus(BaseModel):
    label: str
    masked_key: str
    priority: int


class ProviderStatus(BaseModel):
    model_config = ConfigDict(protected_namespaces=())

    model_name: str
    credentials: list[CredentialStatus]


class LLMSettingsResponse(BaseModel):
    version: int
    mode: DecisionEngineMode
    active_llm_provider: ProviderName | None
    providers: dict[str, ProviderStatus]
    source: Literal["database", "environment", "rules_only"]


class ProviderCatalog(BaseModel):
    id: ProviderName
    label: str
    default_model: str
    models: list[str]


class ModelCatalogResponse(BaseModel):
    version: int
    providers: list[ProviderCatalog]


class CredentialConnectionResult(BaseModel):
    label: str
    priority: int
    connected: bool
    message: str


class LLMConnectionResponse(BaseModel):
    model_config = ConfigDict(protected_namespaces=())

    connected: bool
    saved: bool
    provider: ProviderName
    model_name: str
    credentials: list[CredentialConnectionResult]


class DisconnectRequest(BaseModel):
    provider: ProviderName | None = None
