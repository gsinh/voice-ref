"""12-factor configuration: every setting comes from the environment (factor III)."""

from typing import Literal

from pydantic_settings import BaseSettings, SettingsConfigDict


class ServiceSettings(BaseSettings):
    """Settings every service has. Services subclass this and add their own fields.

    Values come only from environment variables. Compose passes `.env` into the
    container; there is no config file baked into the image.
    """

    model_config = SettingsConfigDict(extra="ignore", frozen=True)

    service_name: str = "service"
    environment: Literal["local", "ci", "production"] = "local"
    log_level: Literal["DEBUG", "INFO", "WARNING", "ERROR"] = "INFO"
    host: str = "0.0.0.0"
    port: int = 8000
