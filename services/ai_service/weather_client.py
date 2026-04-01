from __future__ import annotations

import time
from dataclasses import dataclass

import httpx


@dataclass(frozen=True)
class WeatherResult:
    summary: str
    temperature_c: float | None = None
    city: str | None = None


def _cache_key(lat: float, lon: float) -> str:
    # Round to reduce cache fragmentation & rate spikes.
    return f"{round(lat, 2)}:{round(lon, 2)}"


class WeatherCache:
    def __init__(self) -> None:
        self._items: dict[str, tuple[float, WeatherResult]] = {}

    def get(self, key: str) -> WeatherResult | None:
        item = self._items.get(key)
        if not item:
            return None
        expires_at, value = item
        if time.time() >= expires_at:
            self._items.pop(key, None)
            return None
        return value

    def set(self, key: str, value: WeatherResult, ttl_s: int) -> None:
        self._items[key] = (time.time() + ttl_s, value)


_cache = WeatherCache()


async def fetch_openweather_summary(
    *,
    api_key: str,
    lat: float,
    lon: float,
    lang: str = "en",
    ttl_s: int = 45 * 60,
) -> WeatherResult:
    key = _cache_key(lat, lon)
    cached = _cache.get(key)
    if cached is not None:
        return cached

    params = {
        "lat": lat,
        "lon": lon,
        "appid": api_key,
        "units": "metric",
        "lang": lang,
    }

    async with httpx.AsyncClient(timeout=15) as client:
        res = await client.get("https://api.openweathermap.org/data/2.5/weather", params=params)
        res.raise_for_status()
        data = res.json()

    weather_arr = data.get("weather") or []
    description = ""
    if weather_arr and isinstance(weather_arr, list) and isinstance(weather_arr[0], dict):
        description = str(weather_arr[0].get("description") or "").strip()

    main = data.get("main") or {}
    temp = None
    if isinstance(main, dict):
        t = main.get("temp")
        if isinstance(t, (int, float)):
            temp = float(t)

    city = str(data.get("name") or "").strip() or None

    parts: list[str] = []
    if temp is not None:
        parts.append(f"{round(temp)}°C")
    if description:
        parts.append(description)
    if city:
        parts.append(city)

    summary = ", ".join(parts) if parts else "unknown"
    out = WeatherResult(summary=summary, temperature_c=temp, city=city)
    _cache.set(key, out, ttl_s=ttl_s)
    return out

