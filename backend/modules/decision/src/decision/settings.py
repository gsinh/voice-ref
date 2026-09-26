from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Settings for the decision module. Read from environment variables prefixed `DECISION_`."""

    model_config = SettingsConfigDict(env_prefix="DECISION_", extra="ignore", frozen=True)

    confidence_threshold: float = 0.85
