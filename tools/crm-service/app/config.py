from pydantic_settings import BaseSettings, SettingsConfigDict

class Settings(BaseSettings):
    service_name: str
    service_port: int
    database_url: str
    tool_shared_token: str
    scenario_id: str = "phase2-demo"

    model_config = SettingsConfigDict(
        env_file=".env",
        extra="ignore"
    )

settings = Settings()
