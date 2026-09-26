from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Bank module settings, read from `BANK_`-prefixed env vars."""

    model_config = SettingsConfigDict(env_prefix="BANK_", extra="ignore", frozen=True)

    database_url: str = "postgresql://bank_api:bank@localhost:5432/voiceref"
    pool_max_size: int = 5
