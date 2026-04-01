from __future__ import annotations

import httpx


async def tavily_search(api_key: str, query: str, *, max_results: int = 5) -> list[dict]:
    async with httpx.AsyncClient(timeout=20) as client:
        res = await client.post(
            "https://api.tavily.com/search",
            json={"api_key": api_key, "query": query, "max_results": max_results, "include_answer": False},
        )
        res.raise_for_status()
        data = res.json()
        return data.get("results", []) or []

