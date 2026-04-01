from __future__ import annotations

import httpx


async def groq_chat_completion(api_key: str, *, model: str, system: str, user: str) -> str:
    """
    Minimal Groq OpenAI-compatible chat call.
    """
    headers = {"authorization": f"Bearer {api_key}", "content-type": "application/json"}
    payload = {
        "model": model,
        "messages": [
            {"role": "system", "content": system},
            {"role": "user", "content": user},
        ],
        "temperature": 0.4,
    }
    async with httpx.AsyncClient(timeout=60) as client:
        res = await client.post("https://api.groq.com/openai/v1/chat/completions", headers=headers, json=payload)
        res.raise_for_status()
        data = res.json()
        return (data.get("choices") or [{}])[0].get("message", {}).get("content", "") or ""

