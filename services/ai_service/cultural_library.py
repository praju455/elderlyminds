from __future__ import annotations

from datetime import datetime
from typing import Any


DAY_DEITIES = {
    0: "Shiva",
    1: "Hanuman",
    2: "Ganesha",
    3: "Vishnu",
    4: "Lakshmi",
    5: "Shani",
    6: "Surya",
}


LIBRARY: list[dict[str, Any]] = [
    {
        "id": "ramayana-hanuman-courage",
        "category": "ramayana",
        "title": "Hanuman crosses the ocean",
        "tradition": "Ramayana",
        "summary": "When everyone else hesitated, Hanuman remembered his strength and leapt across the ocean to find Sita. It is a story about courage waking up at the right moment.",
        "moral": "Strength grows when duty is clear.",
        "keywords": ["ramayana", "hanuman", "courage", "sita", "ocean"],
    },
    {
        "id": "ramayana-bharata-loyalty",
        "category": "ramayana",
        "title": "Bharata keeps Rama's sandals on the throne",
        "tradition": "Ramayana",
        "summary": "Bharata refuses to take Rama's place for himself and instead rules in Rama's name with humility. It shows love without greed.",
        "moral": "True love protects what is right.",
        "keywords": ["ramayana", "bharata", "rama", "loyalty", "sandals"],
    },
    {
        "id": "mahabharata-arjuna-focus",
        "category": "mahabharata",
        "title": "Arjuna sees only the eye of the bird",
        "tradition": "Mahabharata",
        "summary": "When asked what he sees, Arjuna says he sees only the bird's eye. His focus becomes his strength.",
        "moral": "Calm focus beats noise and distraction.",
        "keywords": ["mahabharata", "arjuna", "focus", "bird"],
    },
    {
        "id": "gita-duty",
        "category": "gita",
        "title": "Do your duty with a steady heart",
        "tradition": "Bhagavad Gita",
        "summary": "Krishna teaches Arjuna to act with sincerity and leave the result without fear. It is a lesson in steady effort.",
        "moral": "Do the right work and let worry become lighter.",
        "keywords": ["gita", "krishna", "duty", "calm", "arjuna"],
    },
    {
        "id": "kabir-dheere",
        "category": "doha",
        "title": "Dheere dheere re mana",
        "tradition": "Kabir Doha",
        "summary": "Kabir reminds us that everything blooms in its own time. Patience is part of wisdom.",
        "moral": "What matters grows steadily, not instantly.",
        "keywords": ["kabir", "doha", "patience", "dheere"],
        "quote": "Dheere dheere re mana, dheere sab kuch hoye.",
    },
    {
        "id": "hanuman-chalisa-strength",
        "category": "prayer",
        "title": "Hanuman Chalisa for strength",
        "tradition": "Hanuman Chalisa",
        "summary": "A beloved prayer asking for courage, protection, and clear-minded devotion. Many elders return to it for steadiness.",
        "moral": "Prayer can make the heart feel supported.",
        "keywords": ["hanuman chalisa", "prayer", "strength", "hanuman"],
    },
    {
        "id": "panchatantra-lion-rabbit",
        "category": "story",
        "title": "The lion and the clever rabbit",
        "tradition": "Panchatantra",
        "summary": "A tiny rabbit defeats a proud lion through wit instead of force. Intelligence becomes the shield of the weak.",
        "moral": "Wisdom can defeat raw power.",
        "keywords": ["panchatantra", "lion", "rabbit", "clever"],
    },
    {
        "id": "akbar-birbal-crow",
        "category": "story",
        "title": "Birbal counts the crows",
        "tradition": "Akbar-Birbal",
        "summary": "When Akbar asks how many crows are in the city, Birbal answers with playful confidence and leaves room for missing or visiting birds.",
        "moral": "A calm mind answers even tricky questions with grace.",
        "keywords": ["akbar", "birbal", "crow", "wit"],
    },
    {
        "id": "tenali-rama-cats",
        "category": "story",
        "title": "Tenali Rama and the royal cats",
        "tradition": "Tenali Rama",
        "summary": "Tenali exposes a bad plan by showing its real result instead of arguing endlessly. He uses humor to teach wisdom.",
        "moral": "Truth becomes easier to accept when shown clearly.",
        "keywords": ["tenali", "rama", "cats", "humor"],
    },
]


def search_library(query: str, limit: int = 4) -> list[dict[str, Any]]:
    lowered = (query or "").strip().lower()
    if not lowered:
        return LIBRARY[:limit]
    scored: list[tuple[int, dict[str, Any]]] = []
    for item in LIBRARY:
        score = 0
        score += 3 if lowered in str(item.get("title") or "").lower() else 0
        score += 2 if lowered in str(item.get("tradition") or "").lower() else 0
        score += 1 if lowered in str(item.get("category") or "").lower() else 0
        score += sum(1 for keyword in item.get("keywords") or [] if keyword in lowered or lowered in keyword)
        if score > 0:
            scored.append((score, item))
    if not scored:
        return LIBRARY[:limit]
    scored.sort(key=lambda pair: pair[0], reverse=True)
    return [item for _, item in scored[:limit]]


def recommended_for_today(region: str = "", language: str = "") -> dict[str, Any]:
    weekday = datetime.now().weekday()
    lowered_region = (region or "").lower()
    lowered_language = (language or "").lower()
    if "karnataka" in lowered_region or "kannada" in lowered_language:
        return next(item for item in LIBRARY if item["id"] == "hanuman-chalisa-strength")
    if weekday == 1:
        return next(item for item in LIBRARY if item["id"] == "hanuman-chalisa-strength")
    if weekday == 4:
        return next(item for item in LIBRARY if item["id"] == "gita-duty")
    if weekday == 6:
        return next(item for item in LIBRARY if item["id"] == "ramayana-hanuman-courage")
    return next(item for item in LIBRARY if item["id"] == "kabir-dheere")


def build_daily_calendar(*, language: str, region: str, tithi: str, festival: str) -> dict[str, Any]:
    now = datetime.now()
    weekday = now.weekday()
    return {
        "date": now.strftime("%Y-%m-%d"),
        "day_name": now.strftime("%A"),
        "deity": DAY_DEITIES.get(weekday, "Vishnu"),
        "language": language or "English",
        "region": region or "",
        "tithi": tithi or "Unknown",
        "festival": festival or "",
        "recommended": recommended_for_today(region=region, language=language),
    }
