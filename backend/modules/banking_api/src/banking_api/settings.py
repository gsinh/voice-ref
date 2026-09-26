from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Settings for the banking_api module. Read from environment variables prefixed `BANK_`."""

    model_config = SettingsConfigDict(env_prefix="BANK_", extra="ignore", frozen=True)

    database_url: str = "postgresql://bank_api:bank@localhost:5432/voiceref"
