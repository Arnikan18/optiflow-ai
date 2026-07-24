from functools import lru_cache
from typing import Optional

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    service_name: str = "incident-service"
    service_port: int = 8102
    database_url: str = "sqlite:///./data/incident.db"
    tool_shared_token: str = "change-me"
    admin_api_key: Optional[str] = None
    scenario_id: str = "phase2-demo"
    seed_on_startup: bool = True
    crm_service_url: Optional[str] = None
    workforce_service_url: Optional[str] = None
    external_service_timeout_seconds: float = 2.0

    model_config = SettingsConfigDict(env_file=".env", extra="ignore")


@lru_cache
def get_settings() -> Settings:
    return Settings()


settings = get_settings()
