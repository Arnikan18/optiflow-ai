from functools import lru_cache
from pydantic_settings import BaseSettings, SettingsConfigDict

class Settings(BaseSettings):
    app_env: str = "development"
    app_version: str = "4.0"
    database_url: str
    
    llm_provider: str = "gemini"
    gemini_api_key: str = ""
    gemini_model: str = ""
    gemini_timeout_seconds: int = 8
    gemini_max_retries: int = 1
    groq_api_key: str = ""
    groq_model: str = "llama-3.1-8b-instant"
    prompt_version: str = "4.0"
    
    crm_service_url: str = "http://crm-service:8101"
    incident_service_url: str = "http://incident-service:8102"
    workforce_service_url: str = "http://workforce-service:8103"
    communication_service_url: str = "http://communication-service:8104"
    tool_shared_token: str = "change-me"
    admin_api_key: str = ""
    
    tool_timeout_seconds: float = 3.0
    max_tool_retries: int = 2
    tool_retry_initial_delay_ms: int = 500
    
    max_graph_steps: int = 40
    max_clarification_rounds: int = 1
    max_replan_count: int = 5
    saga_poll_max_attempts: int = 5
    saga_poll_interval_seconds: float = 1.0

    optimizer_provider: str = "cp_sat"
    cp_sat_time_limit_seconds: float = 5.0
    cp_sat_random_seed: int = 42
    generate_all_optimization_profiles: bool = True
    optimizer_allow_fallback: bool = False
    optimization_strategy: str | None = None
    solver_time_limit_seconds: float | None = None
    
    sse_heartbeat_seconds: int = 15
    demo_mode: bool = True
    demo_step_delay_ms: int = 250
    demo_portfolio_timeout_seconds: float = 3.0
    demo_health_timeout_seconds: float = 2.0
    demo_allow_failure_injection: bool = True
    
    model_config = SettingsConfigDict(
        env_file=".env",
        extra="ignore"
    )

@lru_cache
def get_settings() -> Settings:
    return Settings()
settings = get_settings()
