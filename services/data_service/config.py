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
class DataSettings:
    port: int = int(_env("DATA_SERVICE_PORT", "8002") or "8002")
    cors_allow_origins: str = _env("CORS_ALLOW_ORIGINS", "*") or "*"
    data_dir: str = _env("DATA_DIR", "data_store") or "data_store"
    store_mode: str = _env("DATA_STORE_MODE", "mongo") or "mongo"
    mongo_uri: str | None = _env("MONGO_URI")
    mongo_db_name: str = _env("MONGO_DB_NAME", "eldermind") or "eldermind"


settings = DataSettings()
