from functools import lru_cache
from pydantic_settings import BaseSettings, SettingsConfigDict

class Settings(BaseSettings):
    app_env: str = "development"
    app_version: str = "4.0"
    database_url: str
    
    gemini_api_key: str = ""
    gemini_model: str = ""
    gemini_timeout_seconds: int = 8
    gemini_max_retries: int = 1
    prompt_version: str = "4.0"
    
    crm_service_url: str
    incident_service_url: str
    workforce_service_url: str
    communication_service_url: str
    tool_shared_token: str
    admin_api_key: str = ""
    
    tool_timeout_seconds: float = 3.0
    max_tool_retries: int = 2
    tool_retry_initial_delay_ms: int = 500
    
    max_graph_steps: int = 40
    max_clarification_rounds: int = 1
    max_replan_count: int = 5
    
    sse_heartbeat_seconds: int = 15
    demo_mode: bool = True
    demo_step_delay_ms: int = 250
    
    model_config = SettingsConfigDict(
        env_file=".env",
        extra="ignore"
    )

@lru_cache
def get_settings() -> Settings:
    return Settings()
settings = get_settings()
