from functools import lru_cache
from typing import Optional

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    service_name: str = "workforce-service"
    service_port: int = 8103
    database_url: str = "sqlite:///./data/workforce.db"
    tool_shared_token: str = "change-me"
    admin_api_key: Optional[str] = None
    scenario_id: str = "phase2-demo"
    seed_on_startup: bool = True
    reservation_ttl_seconds: int = 300
    min_reservation_ttl_seconds: int = 30
    max_reservation_ttl_seconds: int = 3600
    incident_service_url: Optional[str] = None
    external_service_timeout_seconds: float = 2.0

    model_config = SettingsConfigDict(env_file=".env", extra="ignore")


@lru_cache
def get_settings() -> Settings:
    return Settings()


settings = get_settings()
