from functools import lru_cache
from typing import Literal

from pydantic import Field, SecretStr
from pydantic_settings import BaseSettings

from config_kit import settings_config


class Settings(BaseSettings):
    """Voice worker settings. Shared names (LiveKit, LLM key) are read as-is; the rest use
    the `VOICE_` prefix."""

    model_config = settings_config(env_prefix="VOICE_")

    # LiveKit (Cloud by default). The worker connects *out*, so no inbound port is needed.
    livekit_url: str = Field("", validation_alias="LIVEKIT_URL")
    livekit_api_key: SecretStr = Field(SecretStr(""), validation_alias="LIVEKIT_API_KEY")
    livekit_api_secret: SecretStr = Field(SecretStr(""), validation_alias="LIVEKIT_API_SECRET")
    agent_name: str = Field("bank-agent", validation_alias="LIVEKIT_AGENT_NAME")

    # The thinking happens in the orchestrator: voice is just another client of /api/chat.
    orchestrator_url: str = "http://127.0.0.1:7860/api"
    orchestrator_timeout_s: float = 30.0

    # STT: any OpenAI-compatible transcription endpoint. Groq Whisper by default.
    stt_base_url: str = Field("https://api.groq.com/openai/v1", validation_alias="STT_BASE_URL")
    stt_model: str = Field("whisper-large-v3-turbo", validation_alias="STT_MODEL")
    stt_api_key: SecretStr = Field(SecretStr(""), validation_alias="STT_API_KEY")
    llm_api_key: SecretStr = Field(SecretStr(""), validation_alias="LLM_API_KEY")  # STT fallback
    stt_language: str = Field("en", validation_alias="STT_LANGUAGE")

    # TTS: Kokoro locally (free), or any OpenAI-compatible speech endpoint.
    tts_provider: Literal["kokoro", "openai"] = Field("kokoro", validation_alias="TTS_PROVIDER")
    tts_voice: str = Field("af_heart", validation_alias="TTS_VOICE")
    tts_speed: float = Field(1.0, validation_alias="TTS_SPEED")
    tts_base_url: str = Field("", validation_alias="TTS_BASE_URL")
    tts_model: str = Field("", validation_alias="TTS_MODEL")
    tts_api_key: SecretStr = Field(SecretStr(""), validation_alias="TTS_API_KEY")
    kokoro_dir: str = Field("/data/models/kokoro", validation_alias="KOKORO_DIR")
    # fp32 by default: measured ~4x faster than the int8 model on x86 CPUs without VNNI.
    kokoro_model: str = Field("kokoro-v1.0.onnx", validation_alias="KOKORO_MODEL")

    greeting: str = "Welcome to Demo Bank. How can I help you today?"

    def stt_key(self) -> str:
        return (self.stt_api_key.get_secret_value() or self.llm_api_key.get_secret_value()) or ""


@lru_cache
def get_settings() -> Settings:
    return Settings()
