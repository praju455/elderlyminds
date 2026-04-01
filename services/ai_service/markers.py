from __future__ import annotations

import re
from dataclasses import dataclass


_HEALTH_RE = re.compile(r"\[HEALTH_LOG:\s*([^\]]+)\]", re.IGNORECASE)
_MOOD_RE = re.compile(r"\[MOOD_LOG:\s*([^\]]+)\]", re.IGNORECASE)
_ALERT_RE = re.compile(r"\[ALERT:\s*([^\]]+)\]", re.IGNORECASE)


@dataclass(frozen=True)
class ParsedMarkers:
    cleaned_text: str
    health_logs: list[str]
    mood_logs: list[str]
    alerts: list[str]


def parse_markers(text: str) -> ParsedMarkers:
    health = _HEALTH_RE.findall(text or "")
    mood = _MOOD_RE.findall(text or "")
    alerts = _ALERT_RE.findall(text or "")

    cleaned = _HEALTH_RE.sub("", text or "")
    cleaned = _MOOD_RE.sub("", cleaned)
    cleaned = _ALERT_RE.sub("", cleaned)
    cleaned = re.sub(r"\s{2,}", " ", cleaned).strip()

    return ParsedMarkers(
        cleaned_text=cleaned,
        health_logs=[h.strip() for h in health if h.strip()],
        mood_logs=[m.strip() for m in mood if m.strip()],
        alerts=[a.strip() for a in alerts if a.strip()],
    )

