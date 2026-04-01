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
class GatewaySettings:
    cors_allow_origins: str = _env("CORS_ALLOW_ORIGINS", "*") or "*"
    gateway_port: int = int(_env("GATEWAY_PORT", "8010") or "8010")

    ai_service_url: str = _env("AI_SERVICE_URL", "http://127.0.0.1:8001") or "http://127.0.0.1:8001"
    data_service_url: str = _env("DATA_SERVICE_URL", "http://127.0.0.1:8002") or "http://127.0.0.1:8002"
    alerts_service_url: str = _env("ALERTS_SERVICE_URL", "http://127.0.0.1:8003") or "http://127.0.0.1:8003"


settings = GatewaySettings()
