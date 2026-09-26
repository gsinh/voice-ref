from functools import lru_cache

from voiceref_common import ServiceSettings


class Settings(ServiceSettings):
    service_name: str = "orchestrator"
    database_url: str = "postgresql://localhost:5432/voiceref"


@lru_cache
def get_settings() -> Settings:
    return Settings()
