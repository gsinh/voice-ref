from pydantic import Field, SecretStr
from pydantic_settings import BaseSettings

from config_kit import settings_config


class Settings(BaseSettings):
    """MCP module settings, read from `MCP_`-prefixed env vars (plus shared ones)."""

    model_config = settings_config(env_prefix="MCP_")

    # Reached over loopback HTTP even inside the monolith, so the boundary stays real.
    banking_api_url: str = "http://127.0.0.1:7860/bank"
    # Shared with the orchestrator, which issues the tokens this module verifies.
    # Required: the process refuses to start without it (fail fast).
    token_signing_key: SecretStr = Field(validation_alias="TOKEN_SIGNING_KEY")
    bank_timeout_s: float = 5.0
