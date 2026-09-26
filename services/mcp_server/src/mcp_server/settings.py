from functools import lru_cache

from voiceref_common import ServiceSettings


class Settings(ServiceSettings):
    service_name: str = "mcp_server"
    banking_api_url: str = "http://localhost:8001"


@lru_cache
def get_settings() -> Settings:
    return Settings()
