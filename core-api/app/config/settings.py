from functools import lru_cache
from pydantic import Field, model_validator
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
    llm_settings_encryption_key: str = ""
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
    demo_delay_ms: int = 300
    demo_portfolio_timeout_seconds: float = 3.0
    demo_health_timeout_seconds: float = 2.0
    demo_allow_failure_injection: bool = True
    simulation_default_scenario: str | None = None
    simulation_auto_advance: bool = False
    simulation_timezone: str = "UTC"
    simulation_event_callback_url: str | None = None
    simulation_event_timeout_seconds: float = 3.0
    simulation_max_event_retries: int = 2
    simulation_scenario_root: str = "scenarios"

    cold_start_runs: int = Field(default=5, ge=1)
    mature_learning_runs: int = Field(default=20, ge=2)
    preference_confidence_low_threshold: float = Field(default=0.40, ge=0.0, le=1.0)
    preference_confidence_high_threshold: float = Field(default=0.70, ge=0.0, le=1.0)
    preference_profile_weight: float = Field(default=0.70, ge=0.0, le=1.0)
    preference_goal_similarity_weight: float = Field(default=0.30, ge=0.0, le=1.0)
    preference_dominance_factor_weight: float = Field(default=0.60, ge=0.0, le=1.0)
    preference_acceptance_factor_weight: float = Field(default=0.40, ge=0.0, le=1.0)

    @model_validator(mode="after")
    def validate_preference_settings(self) -> "Settings":
        if self.mature_learning_runs <= self.cold_start_runs:
            raise ValueError("MATURE_LEARNING_RUNS must be greater than COLD_START_RUNS")
        if self.preference_confidence_high_threshold <= self.preference_confidence_low_threshold:
            raise ValueError(
                "PREFERENCE_CONFIDENCE_HIGH_THRESHOLD must be greater than "
                "PREFERENCE_CONFIDENCE_LOW_THRESHOLD"
            )
        profile_total = self.preference_profile_weight + self.preference_goal_similarity_weight
        if abs(profile_total - 1.0) > 0.000001:
            raise ValueError(
                "PREFERENCE_PROFILE_WEIGHT and PREFERENCE_GOAL_SIMILARITY_WEIGHT must total 1"
            )
        confidence_total = (
            self.preference_dominance_factor_weight
            + self.preference_acceptance_factor_weight
        )
        if abs(confidence_total - 1.0) > 0.000001:
            raise ValueError(
                "PREFERENCE_DOMINANCE_FACTOR_WEIGHT and "
                "PREFERENCE_ACCEPTANCE_FACTOR_WEIGHT must total 1"
            )
        return self
    
    model_config = SettingsConfigDict(
        env_file=".env",
        extra="ignore"
    )

@lru_cache
def get_settings() -> Settings:
    return Settings()
settings = get_settings()
