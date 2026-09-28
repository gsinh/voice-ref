from pydantic import Field, SecretStr
from pydantic_settings import BaseSettings

from config_kit import settings_config


class Settings(BaseSettings):
    """Orchestrator settings. Module-owned values use the `ORCHESTRATOR_` prefix; values
    shared with other components (LLM, System-1, signing key) use their plain names."""

    model_config = settings_config(env_prefix="ORCHESTRATOR_", populate_by_name=True)

    database_url: str = "postgresql://orchestrator:orchestrator@localhost:5432/voiceref"
    # Other modules, reached over loopback HTTP (ADR-0015). Phase 3 points mcp_url at
    # agentgateway instead (ADR-0017): a config change, not a code change.
    mcp_url: str = "http://127.0.0.1:7860/mcp/"
    bank_api_url: str = "http://127.0.0.1:7860/bank"

    # System 2: any OpenAI-compatible endpoint. Groq by default; Ollama offline
    # (http://host.docker.internal:11434/v1).
    llm_base_url: str = Field("https://api.groq.com/openai/v1", validation_alias="LLM_BASE_URL")
    llm_api_key: SecretStr = Field(SecretStr(""), validation_alias="LLM_API_KEY")
    llm_model: str = Field("openai/gpt-oss-120b", validation_alias="LLM_MODEL")
    llm_timeout_s: float = Field(20.0, validation_alias="LLM_TIMEOUT_S")

    # System 1: anything speaking POST /v1/systemone (Laya sidecar, or hosted Jev).
    system1_enabled: bool = Field(True, validation_alias="SYSTEM1_ENABLED")
    system1_url: str = Field("http://127.0.0.1:8100", validation_alias="SYSTEM1_URL")
    system1_api_key: SecretStr = Field(SecretStr(""), validation_alias="SYSTEM1_API_KEY")
    system1_timeout_s: float = Field(3.0, validation_alias="SYSTEM1_TIMEOUT_S")
    intent_threshold: float = Field(0.85, validation_alias="DECISION_CONFIDENCE_THRESHOLD")
    confirm_threshold: float = Field(0.9, validation_alias="CONFIRMATION_CONFIDENCE_THRESHOLD")

    token_signing_key: SecretStr = Field(validation_alias="TOKEN_SIGNING_KEY")
    session_ttl_s: int = 300
    # Mock OTP (ADR: authentication is simulated). Production would call the bank's IdP.
    demo_otp: str = Field("123456", validation_alias="DEMO_OTP")
    max_otp_attempts: int = 3
