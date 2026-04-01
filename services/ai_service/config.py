from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path


def _load_repo_dotenv() -> None:
    for parent in Path(__file__).resolve().parents:
        env_path = parent / ".env"
        if not env_path.exists():
            continue
        for raw_line in env_path.read_text(encoding="utf-8").splitlines():
            line = raw_line.strip()
            if not line or line.startswith("#") or "=" not in line:
                continue
            name, value = line.split("=", 1)
            name = name.strip()
            value = value.strip().strip('"').strip("'")
            if name and name not in os.environ:
                os.environ[name] = value
        break


_load_repo_dotenv()


def _env(name: str, default: str | None = None) -> str | None:
    v = os.getenv(name)
    if v is None:
        return default
    v = v.strip()
    return v if v else default


@dataclass(frozen=True)
class AISettings:
    port: int = int(_env("AI_SERVICE_PORT", "8001") or "8001")
    cors_allow_origins: str = _env("CORS_ALLOW_ORIGINS", "*") or "*"

    groq_api_key: str | None = _env("GROQ_API_KEY")
    groq_model: str = _env("GROQ_MODEL", "llama-3.3-70b-versatile") or "llama-3.3-70b-versatile"

    tavily_api_key: str | None = _env("TAVILY_API_KEY")

    gemini_api_key: str | None = _env("GEMINI_API_KEY")
    gemini_model: str = _env("GEMINI_MODEL", "gemini-1.5-flash") or "gemini-1.5-flash"
    elevenlabs_api_key: str | None = _env("ELEVENLABS_API_KEY")
    elevenlabs_tts_voice_id: str = _env("ELEVENLABS_TTS_VOICE_ID", "JBFqnCBsd6RMkjVDRZzb") or "JBFqnCBsd6RMkjVDRZzb"
    elevenlabs_tts_model_id: str = _env("ELEVENLABS_TTS_MODEL_ID", "eleven_multilingual_v2") or "eleven_multilingual_v2"
    elevenlabs_stt_model_id: str = _env("ELEVENLABS_STT_MODEL_ID", "scribe_v2") or "scribe_v2"

    openweather_api_key: str | None = _env("OPENWEATHER_API_KEY")
    vedastro_base_url: str = _env("VEDASTRO_BASE_URL", "https://api.vedastro.org") or "https://api.vedastro.org"
    vedastro_ayanamsa: str = _env("VEDASTRO_AYANAMSA", "RAMAN") or "RAMAN"
    default_tz_offset: str = _env("DEFAULT_TZ_OFFSET", "+05:30") or "+05:30"

    media_dir: str = _env("MEDIA_DIR", "backend_media") or "backend_media"
    base_url: str = _env("BASE_URL", "http://127.0.0.1:8010") or "http://127.0.0.1:8010"

    data_service_url: str = _env("DATA_SERVICE_URL", "http://127.0.0.1:8002") or "http://127.0.0.1:8002"
    alerts_service_url: str = _env("ALERTS_SERVICE_URL", "http://127.0.0.1:8003") or "http://127.0.0.1:8003"


settings = AISettings()
