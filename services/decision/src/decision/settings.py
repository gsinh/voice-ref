from functools import lru_cache

from voiceref_common import ServiceSettings


class Settings(ServiceSettings):
    service_name: str = "decision"


@lru_cache
def get_settings() -> Settings:
    return Settings()
