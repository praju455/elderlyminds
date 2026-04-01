from __future__ import annotations

from pathlib import Path


def load_system_prompt() -> str:
    root = Path(__file__).resolve().parents[2]
    candidates = [
        root / "prompt.md",
        root / "SYSTEM_PROMPT.md",
        root / "extra_stuffs" / "prompt.md",
    ]
    for p in candidates:
        if p.exists():
            return p.read_text(encoding="utf-8", errors="ignore")
    return ""

