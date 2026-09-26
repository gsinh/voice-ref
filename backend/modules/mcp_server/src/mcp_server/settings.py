from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Settings for the mcp_server module. Read from environment variables prefixed `MCP_`."""

    model_config = SettingsConfigDict(env_prefix="MCP_", extra="ignore", frozen=True)

    # Reached over loopback HTTP even inside the monolith, so the boundary stays real.
    banking_api_url: str = "http://127.0.0.1:7860/bank"
