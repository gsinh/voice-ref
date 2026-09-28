from pydantic_settings import BaseSettings

from config_kit import settings_config


class Settings(BaseSettings):
    """Bank module settings, read from `BANK_`-prefixed env vars."""

    model_config = settings_config(env_prefix="BANK_")

    database_url: str = "postgresql://bank_api:bank@localhost:5432/voiceref"
    pool_max_size: int = 5
