from functools import lru_cache
from typing import Optional

from pydantic import Field, model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    service_name: str = "communication-service"
    service_port: int = 8104
    environment: str = "development"
    database_url: str = "sqlite:///./data/communication.db"
    log_level: str = "INFO"
    tool_shared_token: str = "change-me"
    admin_api_key: Optional[str] = None
    scenario_id: str = "phase2-demo"
    enable_seed_data: Optional[bool] = None
    seed_on_startup: bool = True
    request_id_header: str = "X-Request-ID"
    max_request_id_length: int = Field(default=128, ge=1, le=512)
    max_page_size: int = Field(default=100, ge=1, le=500)
    assignment_request_ttl_seconds: int = 900
    min_assignment_request_ttl_seconds: int = 30
    max_assignment_request_ttl_seconds: int = 86400
    simulated_delivery_mode: str = "success"
    incident_service_url: Optional[str] = None
    workforce_service_url: Optional[str] = None
    external_service_timeout_seconds: float = 2.0

    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    @model_validator(mode="after")
    def apply_seed_alias(self) -> "Settings":
        if self.enable_seed_data is not None:
            self.seed_on_startup = self.enable_seed_data
        return self


@lru_cache
def get_settings() -> Settings:
    return Settings()


settings = get_settings()
