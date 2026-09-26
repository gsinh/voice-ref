"""12-factor configuration: every setting comes from the environment (factor III)."""

from typing import Literal

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Process-level settings. Each module reads its own prefixed settings separately."""

    model_config = SettingsConfigDict(extra="ignore", frozen=True)

    service_name: str = "backend"
    environment: Literal["local", "ci", "production"] = "local"
    log_level: Literal["DEBUG", "INFO", "WARNING", "ERROR"] = "INFO"
    host: str = "0.0.0.0"
    # 7860 is Hugging Face Spaces' default app port; using it everywhere keeps dev/prod parity.
    port: int = 7860
