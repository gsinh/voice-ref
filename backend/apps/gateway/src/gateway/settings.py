"""12-factor configuration: every setting comes from the environment (factor III)."""

from typing import Literal

from pydantic import Field, SecretStr
from pydantic_settings import BaseSettings

from config_kit import settings_config


class Settings(BaseSettings):
    """Process-level settings. Each module reads its own prefixed settings separately."""

    model_config = settings_config()

    service_name: str = "backend"
    environment: Literal["local", "ci", "production"] = "local"
    log_level: Literal["DEBUG", "INFO", "WARNING", "ERROR"] = "INFO"
    host: str = "0.0.0.0"
    # 7860 is Hugging Face Spaces' default app port; using it everywhere keeps dev/prod parity.
    port: int = 7860
    # Database admin login, used only by the one-off `bootstrap` command (never by the
    # running server). Unset everywhere except where bootstrap runs.
    admin_database_url: SecretStr | None = Field(None, validation_alias="ADMIN_DATABASE_URL")
