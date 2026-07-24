from functools import lru_cache
from typing import Optional

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    service_name: str = "crm-service"
    service_port: int = 8101
    database_url: str = "sqlite:///./data/crm.db"
    tool_shared_token: str = "change-me"
    admin_api_key: Optional[str] = Field(default=None)
    scenario_id: str = "phase2-demo"
    seed_on_startup: bool = True

    model_config = SettingsConfigDict(
        env_file=".env",
        extra="ignore",
    )


@lru_cache
def get_settings() -> Settings:
    return Settings()


settings = get_settings()
