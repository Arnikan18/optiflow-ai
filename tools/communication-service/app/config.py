from functools import lru_cache
from typing import Optional

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    service_name: str = "communication-service"
    service_port: int = 8104
    database_url: str = "sqlite:///./data/communication.db"
    tool_shared_token: str = "change-me"
    admin_api_key: Optional[str] = None
    scenario_id: str = "phase2-demo"
    seed_on_startup: bool = True
    assignment_request_ttl_seconds: int = 900
    min_assignment_request_ttl_seconds: int = 30
    max_assignment_request_ttl_seconds: int = 86400
    simulated_delivery_mode: str = "success"
    incident_service_url: Optional[str] = None
    workforce_service_url: Optional[str] = None
    external_service_timeout_seconds: float = 2.0

    model_config = SettingsConfigDict(env_file=".env", extra="ignore")


@lru_cache
def get_settings() -> Settings:
    return Settings()


settings = get_settings()
