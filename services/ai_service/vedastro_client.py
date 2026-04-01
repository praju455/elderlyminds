from __future__ import annotations

import time
from dataclasses import dataclass
from datetime import datetime, timezone

import httpx


@dataclass(frozen=True)
class TithiFestival:
    tithi: str
    festival: str


def _cache_key(lat: float, lon: float, date_ymd: str, tz_offset: str, ayanamsa: str) -> str:
    return f"{round(lat,2)}:{round(lon,2)}:{date_ymd}:{tz_offset}:{ayanamsa}"


class _DailyCache:
    def __init__(self) -> None:
        self._items: dict[str, tuple[float, TithiFestival]] = {}

    def get(self, key: str) -> TithiFestival | None:
        item = self._items.get(key)
        if not item:
            return None
        expires_at, value = item
        if time.time() >= expires_at:
            self._items.pop(key, None)
            return None
        return value

    def set(self, key: str, value: TithiFestival, ttl_s: int) -> None:
        self._items[key] = (time.time() + ttl_s, value)


_cache = _DailyCache()


def _default_date_ymd(now_utc: datetime | None = None) -> str:
    dt = now_utc or datetime.now(timezone.utc)
    return dt.strftime("%m/%d/%Y")


async def fetch_tithi_festival(
    *,
    base_url: str,
    lat: float,
    lon: float,
    tz_offset: str,
    ayanamsa: str,
    time_hm: str | None = None,
    date_mdy: str | None = None,
    ttl_s: int = 20 * 60 * 60,
) -> TithiFestival:
    """
    Derives today's tithi (and optional festival) using VedAstro.

    We intentionally rely on the stable `AllPlanetData` calculator (which is present
    on the free tier) and compute tithi from Sun/Moon nirayana longitudes:

      tithi_index = floor((moon_lon - sun_lon mod 360) / 12) + 1

    Festival is left blank unless we can reliably extract it from VedAstro payload.
    """
    time_hm = (time_hm or "00:12").strip() or "00:12"
    date_mdy = (date_mdy or _default_date_ymd()).strip() or _default_date_ymd()

    key = _cache_key(lat, lon, date_mdy, tz_offset, ayanamsa)
    cached = _cache.get(key)
    if cached is not None:
        return cached

    url = (
        f"{base_url.rstrip('/')}/api/Calculate/AllPlanetData/"
        f"PlanetName/All/Location/{lat},{lon}/Time/{time_hm}/{date_mdy}/{tz_offset}/Ayanamsa/{ayanamsa}"
    )

    async with httpx.AsyncClient(timeout=20) as client:
        res = await client.get(url)
        res.raise_for_status()
        data = res.json()

    def _extract_lon(planet_name: str) -> float | None:
        payload = data.get("Payload") if isinstance(data, dict) else None
        if not isinstance(payload, dict):
            return None
        apd = payload.get("AllPlanetData")
        if not isinstance(apd, list):
            return None
        for item in apd:
            if not isinstance(item, dict) or planet_name not in item:
                continue
            planet = item.get(planet_name)
            if not isinstance(planet, dict):
                continue
            nir = planet.get("PlanetNirayanaLongitude")
            if isinstance(nir, dict):
                td = nir.get("TotalDegrees")
                if isinstance(td, (int, float)):
                    return float(td)
        return None

    sun_lon = _extract_lon("Sun")
    moon_lon = _extract_lon("Moon")

    tithi_str = ""
    if sun_lon is not None and moon_lon is not None:
        delta = (moon_lon - sun_lon) % 360.0
        idx = int(delta // 12.0) + 1  # 1..30
        # Names: 1-15 repeated; paksha depends on half
        names = [
            "Pratipada",
            "Dvitiya",
            "Tritiya",
            "Chaturthi",
            "Panchami",
            "Shashthi",
            "Saptami",
            "Ashtami",
            "Navami",
            "Dashami",
            "Ekadashi",
            "Dwadashi",
            "Trayodashi",
            "Chaturdashi",
            "Purnima",
        ]
        if idx <= 15:
            paksha = "Shukla"
            name = names[idx - 1]
        else:
            paksha = "Krishna"
            if idx == 30:
                name = "Amavasya"
            else:
                name = names[(idx - 16)]
        tithi_str = f"{paksha} {name} (Tithi {idx})"

    # Festival is not reliably available from this calculator; keep blank for now.
    out = TithiFestival(tithi=tithi_str, festival="")
    _cache.set(key, out, ttl_s=ttl_s)
    return out

