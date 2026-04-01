from __future__ import annotations

from typing import Any

import httpx


async def gemini_generate_text(*, api_key: str, model: str, system: str, user: str) -> str:
    """
    Minimal Gemini text generation using Google Generative Language API.
    We keep it dependency-free (httpx only) and return plain text.
    """
    url = f"https://generativelanguage.googleapis.com/v1beta/models/{model}:generateContent"
    params = {"key": api_key}
    body: dict[str, Any] = {
        "contents": [
            {"role": "user", "parts": [{"text": f"SYSTEM:\n{system}\n\nUSER:\n{user}"}]},
        ],
        "generationConfig": {
            "temperature": 0.6,
            "maxOutputTokens": 220,
        },
    }
    async with httpx.AsyncClient(timeout=45) as client:
        res = await client.post(url, params=params, json=body)
        res.raise_for_status()
        data = res.json()
    # Extract first candidate text
    candidates = data.get("candidates") or []
    if not candidates:
        return ""
    content = candidates[0].get("content") if isinstance(candidates[0], dict) else None
    parts = content.get("parts") if isinstance(content, dict) else None
    if isinstance(parts, list) and parts and isinstance(parts[0], dict):
        return str(parts[0].get("text") or "")
    return ""

