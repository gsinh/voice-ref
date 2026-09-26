from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Orchestrator module settings, read from `ORCHESTRATOR_`-prefixed env vars."""

    model_config = SettingsConfigDict(env_prefix="ORCHESTRATOR_", extra="ignore", frozen=True)

    database_url: str = "postgresql://orchestrator:orchestrator@localhost:5432/voiceref"
