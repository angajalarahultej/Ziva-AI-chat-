"""Central settings. Everything secret/configurable comes from the single .env file."""
from pathlib import Path
from pydantic_settings import BaseSettings, SettingsConfigDict

_ASTRA_ROOT = Path(__file__).resolve().parents[3]  # astra/
_ENV_FILE = _ASTRA_ROOT / ".env"


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=str(_ENV_FILE), env_file_encoding="utf-8", extra="ignore")

    LLM_PROVIDER: str = "openrouter"
    LLM_MODEL: str = "nex-agi/nex-n2.5-mini:free"
    LLM_FALLBACK_MODEL: str = "nvidia/nemotron-3-nano-omni-30b-a3b-reasoning:free"
    LLM_MAX_TOKENS: int = 150
    LLM_TEMPERATURE: float = 0.7
    # Local model (Ollama) — set LLM_PROVIDER=ollama to use, no key needed
    LLM_LOCAL_URL: str = "http://localhost:11434"
    LLM_LOCAL_MODEL: str = "gemma3:4b"
    OPENROUTER_API_KEY: str = ""
    OPENROUTER_BASE_URL: str = "https://openrouter.ai/api/v1"
    OPENROUTER_HTTP_REFERER: str = "http://localhost:5173"
    OPENROUTER_APP_TITLE: str = "Ziva"

    STT_PROVIDER: str = "whisper_local"
    STT_MODEL_SIZE: str = "base"
    STT_DEVICE: str = "auto"
    # False = skip the ~3s noise-cleaning pass (faster; needs a quiet room)
    STT_DENOISE: bool = False

    TTS_PROVIDER: str = "edge"
    # Default speaker: "Female" (sweet Indian) or "Male". Per-client override via WS.
    TTS_VOICE: str = "Female"
    TTS_VOICE_EN: str = "en-IN-NeerjaNeural"
    TTS_VOICE_TE: str = "te-IN-ShrutiNeural"
    TTS_VOICE_HI: str = "hi-IN-AnanyaNeural"
    TTS_RATE: str = "+0%"
    TTS_VOLUME: str = "+0%"

    ASTRA_GREETING_EN: str = "Good morning. I'm Ziva. I'm ready to talk."
    ASTRA_GREETING_TE: str = "నమస్తే! నేను Ziva. మాట్లాడటానికి సిద్ధంగా ఉన్నాను."
    DEFAULT_LANGUAGE: str = "AUTO"
    DATABASE_URL: str = "sqlite:///./data/astra.db"
    DEBUG: bool = False
    BACKEND_PORT: int = 8000


settings = Settings()
