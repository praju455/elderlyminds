from __future__ import annotations

import logging
import re
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import httpx
from fastapi import FastAPI, Request, UploadFile

logger = logging.getLogger("ai_service")
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from fastapi.staticfiles import StaticFiles

from .config import settings
from .cultural_library import build_daily_calendar, search_library
from .emotion import infer_emotion_from_audio_bytes
from .gemini_client import gemini_generate_text
from .groq_client import groq_chat_completion
from .markers import ParsedMarkers, parse_markers
from .prompt_loader import load_system_prompt
from .rppg_analysis import analyze_rppg_video_bytes
from .stt import transcribe_audio_bytes
from .tavily_client import tavily_search
from .tts import synthesize_mp3
from .vedastro_client import fetch_tithi_festival
from .pdf_report import generate_wellness_pdf
from .weather_client import fetch_openweather_summary


app = FastAPI(title="ElderMind AI Service", version="0.2.0")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"] if settings.cors_allow_origins == "*" else settings.cors_allow_origins.split(","),
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

Path(settings.media_dir).mkdir(parents=True, exist_ok=True)
app.mount("/media", StaticFiles(directory=settings.media_dir), name="media")


HEALTH_PATTERNS: dict[str, tuple[str, ...]] = {
    # English + Hindi + Kannada + Tamil + Telugu + Marathi + Gujarati
    "headache": ("headache", "head", "chakra", "sar dard", "sir dard",
                 "tale novu", "தலைவலி", "తలనొప్పి", "डोकेदुखी", "માથું દુખે"),
    "knee_pain": ("knee", "ghutna", "joint pain", "mandi novu", "முட்டி வலி",
                  "మోకాలు నొప్పి", "गुडघा दुखी", "ઘૂંટણ દુખે"),
    "chest_pain": ("chest pain", "chest", "seene", "heart pain", "ene novu",
                   "நெஞ்சு வலி", "ఛాతి నొప్పి", "छाती दुखी", "છાતી દુખે"),
    "breathing": ("breath", "saans", "breathing", "suffocation", "ushiratagatilla",
                  "மூச்சு", "ఊపిరి", "श्वास", "શ્વાસ"),
    "dizziness": ("dizzy", "dizziness", "chakkar", "tale suttu", "தலைச்சுற்று",
                  "తలతిరుగుతోంది", "चक्कर", "ચક્કર"),
    "nausea": ("nausea", "jee machal", "vomit feel", "vakarike", "குமட்டல்",
               "వాంతి", "मळमळ", "ઉબકા"),
    "vomiting": ("vomit", "ulthi", "throwing up", "vaanti", "வாந்தி",
                 "వాంతి", "उलटी", "ઉલ્ટી"),
    "fever": ("fever", "bukhar", "temperature", "jwara", "காய்ச்சல்",
              "జ్వరం", "ताप", "તાવ"),
    "appetite_low": ("no appetite", "bhook", "not eating", "oota beda",
                     "பசி இல்லை", "ఆకలి లేదు", "भूक नाही", "ભૂખ નથી"),
    "sleep_poor": ("sleep", "neend nahi", "could not sleep", "nidde baralla",
                   "தூக்கமில்லை", "నిద్ర రాలేదు", "झोप नाही", "ઊંઘ નથી"),
    "fatigue": ("tired", "fatigue", "thakaan", "no energy", "sust",
                "thakthu", "களைப்பு", "అలసట", "थकवा", "થાક"),
    "confusion": ("confused", "bhool", "forgetting", "samajh nahi", "marethu",
                  "மறந்துவிட்டேன்", "మర్చిపోయాను", "विसरतो", "ભૂલી ગયો"),
    "fall": ("fell", "fall", "gir gaya", "gir gayi", "biddenu", "bidde",
             "விழுந்தேன்", "పడిపోయాను", "पडलो", "પડી ગયો"),
}

LOW_MOOD_TERMS = ("alone", "akela", "lonely", "miss", "sad", "udaas", "kuch achha nahi")
ANXIOUS_TERMS = ("worried", "tension", "anxious", "dar", "panic", "money", "hospital")
GOOD_MOOD_TERMS = ("happy", "accha", "good", "great", "story", "joke", "prayer")
HINDI_TERMS = ("aap", "kya", "kaise", "haan", "ji", "paani", "dard", "acha", "accha", "thoda", "main", "mera")
KANNADA_TERMS = ("nimma", "hegiddira", "neeru", "oota", "beda", "dayavittu", "amma", "appa")
TAMIL_TERMS = ("eppadi", "saptingla", "thanni", "amma", "appa", "venuma", "seri")
TELUGU_TERMS = ("ela", "bagunnara", "neellu", "amma", "nanna", "andi")
MARATHI_TERMS = ("tumhi", "kasa", "pani", "baray", "ahe", "kaay", "मला", "आहे", "डोके", "थोडंसं")
GUJARATI_TERMS = ("kem", "cho", "paani", "saru", "chhe", "tame")


def _browser_lang_for_code(code: str) -> str:
    return {
        "hi": "hi-IN",
        "kn": "kn-IN",
        "ta": "ta-IN",
        "te": "te-IN",
        "gu": "gu-IN",
        "mr": "mr-IN",
    }.get(code, "en-IN")


def _contains_codepoint(text: str, start: int, end: int) -> bool:
    return any(start <= ord(ch) <= end for ch in text)


def _default_coords_for_region(region: str) -> tuple[float, float]:
    lowered = (region or "").strip().lower()
    if "karnataka" in lowered:
        return 12.9716, 77.5946
    if "tamil" in lowered:
        return 13.0827, 80.2707
    if "maharashtra" in lowered:
        return 19.076, 72.8777
    if "gujarat" in lowered:
        return 23.0225, 72.5714
    if "uttar" in lowered or "bihar" in lowered:
        return 26.8467, 80.9462
    return 12.9716, 77.5946


@app.get("/health")
async def health():
    return {"status": "ok", "service": "ai"}


def _lang_for_user(profile: dict[str, Any]) -> tuple[str, str]:
    language = str(profile.get("language") or "Hindi").strip().lower()
    if "kannada" in language:
        return "kn", "Kannada"
    if "tamil" in language:
        return "ta", "Tamil"
    if "telugu" in language:
        return "te", "Telugu"
    if "gujarati" in language:
        return "gu", "Gujarati"
    if "marathi" in language:
        return "mr", "Marathi"
    if "hindi" in language:
        return "hi", "Hindi"
    return "en", "English"


def _detect_runtime_language(user_text: str, profile: dict[str, Any]) -> tuple[str, str]:
    cleaned = _clean_text(user_text)
    if not cleaned:
        return _lang_for_user(profile)

    lowered = cleaned.lower()
    if _contains_codepoint(cleaned, 0x0C80, 0x0CFF):
        return "kn", "Kannada"
    if _contains_codepoint(cleaned, 0x0B80, 0x0BFF):
        return "ta", "Tamil"
    if _contains_codepoint(cleaned, 0x0C00, 0x0C7F):
        return "te", "Telugu"
    if _contains_codepoint(cleaned, 0x0A80, 0x0AFF):
        return "gu", "Gujarati"
    if _contains_codepoint(cleaned, 0x0900, 0x097F):
        if sum(term in lowered for term in MARATHI_TERMS) > sum(term in lowered for term in HINDI_TERMS):
            return "mr", "Marathi"
        return "hi", "Hindi"

    scored = {
        "hi": sum(term in lowered for term in HINDI_TERMS),
        "kn": sum(term in lowered for term in KANNADA_TERMS),
        "ta": sum(term in lowered for term in TAMIL_TERMS),
        "te": sum(term in lowered for term in TELUGU_TERMS),
        "mr": sum(term in lowered for term in MARATHI_TERMS),
        "gu": sum(term in lowered for term in GUJARATI_TERMS),
    }
    best_code = max(scored, key=scored.get)
    if scored[best_code] > 0:
        return {
            "hi": ("hi", "Hindi"),
            "kn": ("kn", "Kannada"),
            "ta": ("ta", "Tamil"),
            "te": ("te", "Telugu"),
            "mr": ("mr", "Marathi"),
            "gu": ("gu", "Gujarati"),
        }[best_code]
    return _lang_for_user(profile)


def _clean_text(text: str) -> str:
    return re.sub(r"\s+", " ", (text or "")).strip()


def _detect_health_logs(user_text: str) -> list[str]:
    lowered = user_text.lower()
    found: list[str] = []
    for label, keywords in HEALTH_PATTERNS.items():
        if any(term in lowered for term in keywords):
            found.append(label)
    return found


def _derive_mood(user_text: str, emotion_label: str, parsed: ParsedMarkers) -> str:
    if parsed.mood_logs:
        return parsed.mood_logs[-1]
    lowered = user_text.lower()
    if any(term in lowered for term in LOW_MOOD_TERMS):
        return "low"
    if any(term in lowered for term in ANXIOUS_TERMS):
        return "anxious"
    if any(term in lowered for term in GOOD_MOOD_TERMS):
        return "good"
    if emotion_label in {"sad", "fear", "angry"}:
        return "low" if emotion_label == "sad" else "anxious"
    return "okay"


def _count_low_days(recent_conversations: list[dict[str, Any]]) -> int:
    low_days: set[str] = set()
    for item in recent_conversations:
        mood = str(item.get("mood") or "").lower()
        ts = str(item.get("ts") or "")
        if mood == "low" and len(ts) >= 10:
            low_days.add(ts[:10])
    return len(low_days)


def _derive_alerts(
    user_text: str,
    health_logs: list[str],
    mood: str,
    parsed: ParsedMarkers,
    recent_conversations: list[dict[str, Any]],
) -> list[str]:
    alerts = list(parsed.alerts)
    urgent_health = {"chest_pain", "breathing", "confusion", "fall", "vomiting"}
    if any(issue in urgent_health for issue in health_logs):
        alerts.append("urgent_health")
    if mood == "low" and _count_low_days(recent_conversations[-30:]) >= 3:
        alerts.append("mood_pattern_low")
    lowered = user_text.lower()
    if any(term in lowered for term in ("emergency", "sos", "help me", "call someone")):
        alerts.append("urgent_help")
    # preserve order while deduplicating
    seen: set[str] = set()
    unique: list[str] = []
    for item in alerts:
        if item in seen:
            continue
        seen.add(item)
        unique.append(item)
    return unique


def _extract_memories(user_text: str, profile: dict[str, Any]) -> list[dict[str, Any]]:
    text = _clean_text(user_text)
    lowered = text.lower()
    memories: list[dict[str, Any]] = []

    match = re.search(r"\bmy son is ([A-Za-z]+)|mera beta ([A-Za-z]+)", text, re.IGNORECASE)
    if match:
        name = match.group(1) or match.group(2)
        if name:
            memories.append({"fact": f"Son's name is {name}", "category": "family"})

    if "i like" in lowered:
        fact = text.split("like", 1)[-1].strip(" .")
        if fact:
            memories.append({"fact": f"Likes {fact}", "category": "preference"})

    if any(term in lowered for term in LOW_MOOD_TERMS):
        caretaker = profile.get("caretaker_name") or profile.get("caregiver_name") or "family"
        memories.append({"fact": f"Feels lonely and misses {caretaker}", "category": "emotion"})

    if "pray" in lowered or "chalisa" in lowered or "doha" in lowered:
        memories.append({"fact": "Enjoys spiritual content", "category": "preference"})

    return memories


def _fallback_reply(
    user_text: str,
    profile: dict[str, Any],
    mood: str,
    health_logs: list[str],
    alerts: list[str],
    response_lang_code: str,
) -> str:
    import random

    name = str(profile.get("name") or "Friend")

    # --- contextual (non-random) replies take priority -----------------------
    if response_lang_code == "en":
        if "doha" in user_text.lower():
            return f"{name}, here is a gentle doha: slowly and with patience, everything comes in time. [MOOD_LOG: good]"
        if "prayer" in user_text.lower() or "chalisa" in user_text.lower():
            return f"{name}, let us say a short prayer together. I am here with you. [MOOD_LOG: good]"
        if "fall" in health_logs or "urgent_health" in alerts:
            return f"{name}, I am with you. I am telling your support person right now. [ALERT: urgent_health]"
        if "headache" in health_logs:
            return f"{name}, a headache feels hard. Please rest a little and drink some water. [HEALTH_LOG: headache]"
    elif response_lang_code not in ("kn", "ta", "te", "gu", "mr"):
        # Hindi / default contextual checks
        if "doha" in user_text.lower():
            return f"{name} ji, suno: Dhire dhire re mana, dhire sab kuch hoye. Sab kuch apne samay par hota hai. [MOOD_LOG: good]"
        if "prayer" in user_text.lower() or "chalisa" in user_text.lower():
            return f"{name} ji, chalo ek chhoti prarthana saath karte hain. Main hoon, aap aaraam se suno. [MOOD_LOG: good]"
        if "fall" in health_logs or "urgent_health" in alerts:
            return f"{name} ji, main aapke saath hoon. Main ab caretaker ko bata raha hoon. [ALERT: urgent_health]"
        if "headache" in health_logs:
            return f"{name} ji, sar dard mushkil hota hai. Thoda rest kijiye aur paani pee lijiye. [HEALTH_LOG: headache]"

    # --- randomised pools so the elder never hears the same line twice -------
    _pools: dict[str, dict[str, list[str]]] = {
        "en": {
            "low": [
                f"{name}, it feels lonely, na. Talk to me, I am right here. [MOOD_LOG: low]",
                f"{name}, I know it is hard sometimes. I am not going anywhere. [MOOD_LOG: low]",
                f"{name}, you are not alone. Tell me what is on your mind. [MOOD_LOG: low]",
            ],
            "anxious": [
                f"{name}, do not worry, we will take this one step at a time. I am with you. [MOOD_LOG: anxious]",
                f"{name}, take a deep breath with me. Everything will be alright. [MOOD_LOG: anxious]",
                f"{name}, let us slow down together. There is no rush. [MOOD_LOG: anxious]",
            ],
            "okay": [
                f"{name}, I am listening. Please speak slowly. [MOOD_LOG: okay]",
                f"{name}, I am here whenever you want to talk. [MOOD_LOG: okay]",
                f"{name}, tell me more, I am all ears. [MOOD_LOG: okay]",
                f"{name}, take your time, I am right here with you. [MOOD_LOG: okay]",
            ],
        },
        "kn": {
            "low": [
                f"{name} avare, ಒಂಟಿಯಾಗಿದೆಯೇ? ನಾನು ಇಲ್ಲಿದ್ದೇನೆ. [MOOD_LOG: low]",
                f"{name} avare, ನಿಮಗೆ ಕಷ್ಟವಾಗಿದೆ ಎಂದು ಗೊತ್ತು. ನಾನು ಜೊತೆಗಿದ್ದೇನೆ. [MOOD_LOG: low]",
            ],
            "anxious": [
                f"{name} avare, ಚಿಂತಿಸಬೇಡಿ. ನಿಧಾನವಾಗಿ ನೋಡೋಣ. [MOOD_LOG: anxious]",
                f"{name} avare, ಒಂದು ದೀರ್ಘ ಉಸಿರು ತೆಗೆದುಕೊಳ್ಳಿ. ಎಲ್ಲಾ ಸರಿಯಾಗುತ್ತದೆ. [MOOD_LOG: anxious]",
            ],
            "okay": [
                f"{name} avare, ನಾನು ಕೇಳುತ್ತಿದ್ದೇನೆ. ಆರಾಮವಾಗಿ ಹೇಳಿ. [MOOD_LOG: okay]",
                f"{name} avare, ಹೇಳಿ, ನಾನು ಇಲ್ಲೇ ಇದ್ದೇನೆ. [MOOD_LOG: okay]",
            ],
        },
        "ta": {
            "low": [
                f"{name}, தனியாக இருக்கிற மாதிரி தோன்றுகிறதா? நான் இருக்கிறேன். [MOOD_LOG: low]",
                f"{name}, கஷ்டமா இருக்கு என்று தெரியும். நான் உங்கள் பக்கத்தில் இருக்கிறேன். [MOOD_LOG: low]",
            ],
            "anxious": [
                f"{name}, கவலைப்பட வேண்டாம். நிதானமாக பார்க்கலாம். [MOOD_LOG: anxious]",
                f"{name}, ஒரு பெரிய மூச்சு எடுங்கள். எல்லாம் சரியாகும். [MOOD_LOG: anxious]",
            ],
            "okay": [
                f"{name}, நான் கேட்டு கொண்டிருக்கிறேன். அமைதியாக சொல்லுங்கள். [MOOD_LOG: okay]",
                f"{name}, சொல்லுங்கள், நான் இங்கே இருக்கிறேன். [MOOD_LOG: okay]",
            ],
        },
        "te": {
            "low": [
                f"{name} garu, ఒంటరిగా అనిపిస్తున్నదా? నేను మీతోనే ఉన్నాను. [MOOD_LOG: low]",
                f"{name} garu, కష్టంగా ఉందని తెలుసు. నేను ఇక్కడే ఉన్నాను. [MOOD_LOG: low]",
            ],
            "anxious": [
                f"{name} garu, ఆందోళన పడకండి. నెమ్మదిగా చూద్దాం. [MOOD_LOG: anxious]",
                f"{name} garu, ఒక పెద్ద శ్వాస తీసుకోండి. అంతా బాగవుతుంది. [MOOD_LOG: anxious]",
            ],
            "okay": [
                f"{name} garu, నేను వింటున్నాను. నెమ్మదిగా చెప్పండి. [MOOD_LOG: okay]",
                f"{name} garu, చెప్పండి, నేను ఇక్కడే ఉన్నాను. [MOOD_LOG: okay]",
            ],
        },
        "gu": {
            "low": [
                f"{name}, એકલું લાગી રહ્યું છે ને? હું અહીં છું. [MOOD_LOG: low]",
                f"{name}, મુશ્કેલ છે એ ખબર છે. હું તમારી સાથે છું. [MOOD_LOG: low]",
            ],
            "anxious": [
                f"{name}, ચિંતા ન કરો. ધીમે ધીમે જોઈએ. [MOOD_LOG: anxious]",
                f"{name}, એક ઊંડો શ્વાસ લો. બધું સારું થશે. [MOOD_LOG: anxious]",
            ],
            "okay": [
                f"{name}, હું સાંભળી રહ્યો છું. આરામથી કહો. [MOOD_LOG: okay]",
                f"{name}, કહો, હું અહીં છું. [MOOD_LOG: okay]",
            ],
        },
        "mr": {
            "low": [
                f"{name}, एकटं वाटत आहे ना? मी इथेच आहे. [MOOD_LOG: low]",
                f"{name}, कठीण आहे हे माहीत आहे. मी तुमच्या सोबत आहे. [MOOD_LOG: low]",
            ],
            "anxious": [
                f"{name}, काळजी करू नका. आपण हळूहळू पाहू. [MOOD_LOG: anxious]",
                f"{name}, एक मोठा श्वास घ्या. सर्व ठीक होईल. [MOOD_LOG: anxious]",
            ],
            "okay": [
                f"{name}, मी ऐकत आहे. शांतपणे सांगा. [MOOD_LOG: okay]",
                f"{name}, सांगा, मी इथे आहे. [MOOD_LOG: okay]",
            ],
        },
    }
    # Hindi / default pool
    _pools["hi"] = {
        "low": [
            f"{name} ji, akela lag raha hai na. Baat kariye, main yahin hoon. [MOOD_LOG: low]",
            f"{name} ji, mushkil waqt hai, lekin main saath hoon. [MOOD_LOG: low]",
            f"{name} ji, aap akele nahi hain. Main hamesha yahin hoon. [MOOD_LOG: low]",
        ],
        "anxious": [
            f"{name} ji, chinta mat kijiye, hum ek-ek baat dheere se dekhenge. Main saath hoon. [MOOD_LOG: anxious]",
            f"{name} ji, ek lambi saans lijiye. Sab theek hoga. [MOOD_LOG: anxious]",
            f"{name} ji, dheere dheere chalte hain. Koi jaldi nahi hai. [MOOD_LOG: anxious]",
        ],
        "okay": [
            f"{name} ji, main sun raha hoon. Aap aaraam se boliye. [MOOD_LOG: okay]",
            f"{name} ji, bataaiye, main yahin hoon. [MOOD_LOG: okay]",
            f"{name} ji, aapki baat sun raha hoon. Jab chahe boliye. [MOOD_LOG: okay]",
            f"{name} ji, koi jaldi nahi, aaraam se boliye. [MOOD_LOG: okay]",
        ],
    }

    lang = response_lang_code if response_lang_code in _pools else "hi"
    pool = _pools[lang]
    bucket = mood if mood in pool else "okay"
    return random.choice(pool[bucket])


def _fallback_report_analysis(report_text: str, profile: dict[str, Any]) -> dict[str, str]:
    cleaned = _clean_text(report_text)
    snippet = cleaned[:320] if cleaned else "No readable report text was found."
    preferences = ", ".join(profile.get("preferences") or []) or "No stored care preferences yet."
    return {
        "summary": f"Bhumi found these main report notes: {snippet}",
        "advice": (
            "Please verify the report with the doctor, update medicines or reminders only if they were clearly prescribed, "
            f"and keep these comfort preferences in mind: {preferences}"
        ),
    }


def _parse_report_analysis(raw: str, report_text: str, profile: dict[str, Any]) -> dict[str, str]:
    cleaned = _clean_text(raw)
    if not cleaned:
        return _fallback_report_analysis(report_text, profile)

    summary = ""
    advice = ""
    summary_match = re.search(r"summary\s*:\s*(.+?)(?:advice\s*:|$)", cleaned, re.IGNORECASE)
    advice_match = re.search(r"advice\s*:\s*(.+)$", cleaned, re.IGNORECASE)
    if summary_match:
        summary = summary_match.group(1).strip(" -")
    if advice_match:
        advice = advice_match.group(1).strip(" -")
    if not summary and not advice:
        parts = [part.strip(" -") for part in re.split(r"(?:\n|;)", raw) if part.strip()]
        summary = parts[0] if parts else ""
        advice = parts[1] if len(parts) > 1 else ""
    if not summary or not advice:
        fallback = _fallback_report_analysis(report_text, profile)
        summary = summary or fallback["summary"]
        advice = advice or fallback["advice"]
    return {"summary": summary, "advice": advice}


def _fallback_medicine_suggestions(report_text: str) -> list[dict[str, Any]]:
    suggestions: list[dict[str, Any]] = []
    seen: set[str] = set()
    for line in str(report_text or "").splitlines():
        cleaned = _clean_text(line)
        if not cleaned:
            continue
        match = re.search(r"(?:tab|tablet|cap|capsule|syrup)?\s*([A-Za-z][A-Za-z0-9 +.-]{2,40})\s+(\d+(?:\.\d+)?\s*(?:mg|ml|mcg|g))", cleaned, re.IGNORECASE)
        if not match:
            continue
        name = match.group(1).strip(" .,-")
        dose = match.group(2).strip()
        key = f"{name.lower()}::{dose.lower()}"
        if key in seen:
            continue
        seen.add(key)
        suggestions.append(
            {
                "name": name,
                "dose": dose,
                "times": [],
                "instructions": "",
                "condition": "",
            }
        )
    return suggestions[:8]


def _parse_medicine_suggestions(raw: str, report_text: str) -> list[dict[str, Any]]:
    suggestions: list[dict[str, Any]] = []
    for line in str(raw or "").splitlines():
        cleaned = _clean_text(line)
        if not cleaned:
            continue
        parts = [part.strip() for part in cleaned.split("|")]
        if len(parts) < 2:
            continue
        name = parts[0]
        dose = parts[1]
        times = [item.strip() for item in (parts[2] if len(parts) > 2 else "").split(",") if item.strip()]
        instructions = parts[3] if len(parts) > 3 else ""
        condition = parts[4] if len(parts) > 4 else ""
        if not name or not dose:
            continue
        suggestions.append(
            {
                "name": name,
                "dose": dose,
                "times": times,
                "instructions": instructions,
                "condition": condition,
            }
        )
    return suggestions or _fallback_medicine_suggestions(report_text)


async def _fetch_user_context(user_id: str) -> dict[str, Any]:
    async with httpx.AsyncClient(timeout=12) as client:
        user_res = await client.get(f"{settings.data_service_url}/user/{user_id}")
        meds_res = await client.get(f"{settings.data_service_url}/medicine/{user_id}")
        conv_res = await client.get(f"{settings.data_service_url}/conversations/{user_id}", params={"limit": 12})
        memory_res = await client.get(f"{settings.data_service_url}/memory/{user_id}", params={"limit": 12})
        activity_res = await client.get(f"{settings.data_service_url}/activity/{user_id}")

    return {
        "user": (user_res.json() or {}).get("user") or {"user_id": user_id},
        "medicines": (meds_res.json() or {}).get("medicines") or [],
        "recent_conversations": (conv_res.json() or {}).get("items") or [],
        "memories": (memory_res.json() or {}).get("items") or [],
        "activity": (activity_res.json() or {}).get("activity") or {},
    }


def _build_system_prompt(
    *,
    base_prompt: str,
    profile: dict[str, Any],
    medicines: list[dict[str, Any]],
    memories: list[dict[str, Any]],
    recent_conversations: list[dict[str, Any]],
    mood: str,
    weather_summary: str,
    festival_today: str,
    tithi_today: str,
    response_language_name: str,
) -> str:
    medicine_lines = ", ".join(
        f"{med.get('name', 'Medicine')} at {', '.join(med.get('times') or [])}" for med in medicines[:8]
    ) or "None listed"
    memory_lines = "\n".join(f"- {item.get('fact')}" for item in memories[-10:] if item.get("fact")) or "- No stored memories yet"
    conversation_lines = "\n".join(
        f"- User: {item.get('text_input', '')} | Assistant: {item.get('ai_response', '')}"
        for item in recent_conversations[-10:]
    ) or "- No recent history"
    conditions = ", ".join(profile.get("conditions") or []) or "None known"
    allergies = ", ".join(profile.get("allergies") or []) or "None known"
    current_time = datetime.now().astimezone().strftime("%H:%M")
    current_date = datetime.now().astimezone().strftime("%Y-%m-%d")

    injected = f"""

LIVE_CONTEXT:
USER PROFILE:
  Name:             {profile.get('name', 'Friend')}
  Age:              {profile.get('age', 72)}
  Language:         {profile.get('language', 'Hindi')}
  Region:           {profile.get('region', 'Karnataka')}
  Wake Time:        {profile.get('wake_time', '07:00')}
  Sleep Time:       {profile.get('sleep_time', '21:00')}

MEDICAL:
  Conditions:       {conditions}
  Medicines:        {medicine_lines}
  Allergies:        {allergies}

CURRENT STATUS:
  Time:             {current_time}
  Date:             {current_date}
  Mood (detected):  {mood}
  Weather:          {weather_summary}
  Festival Today:   {festival_today or 'None'}
  Tithi Today:      {tithi_today or 'Unknown'}

MEMORY:
{memory_lines}

RECENT HISTORY:
{conversation_lines}

RUNTIME RULES:
- Reply in at most 2 short sentences.
- Reply in {response_language_name} and match the user's latest message language and script.
- Use silent markers when relevant: [HEALTH_LOG: x] [MOOD_LOG: x] [ALERT: x]
- Never say you are an AI.
- Be warm, simple, patient, and natural.
"""
    return base_prompt + injected


async def _post_caretaker_alert(user_id: str, reason: str) -> None:
    try:
        async with httpx.AsyncClient(timeout=12) as client:
            await client.post(
                f"{settings.alerts_service_url}/sos",
                json={
                    "user_id": user_id,
                    "reason": reason,
                    "source": "ai_service",
                },
            )
    except Exception:
        logger.exception("CRITICAL: Failed to send caretaker alert for user=%s reason=%s", user_id, reason)


@app.get("/culture/library")
async def culture_library(q: str = "", category: str = ""):
    query = (q or category or "").strip()
    items = search_library(query, limit=12)
    if category:
      items = [item for item in items if str(item.get("category") or "").lower() == category.strip().lower()] or items
    return {"status": "success", "items": items}


@app.get("/culture/daily/{user_id}")
async def culture_daily(user_id: str):
    context = await _fetch_user_context(user_id)
    profile = context["user"]
    lat = profile.get("lat")
    lon = profile.get("lon")
    try:
        lat_f = float(lat) if lat is not None else None
        lon_f = float(lon) if lon is not None else None
    except Exception:
        lat_f, lon_f = None, None
    if lat_f is None or lon_f is None:
        lat_f, lon_f = _default_coords_for_region(str(profile.get("region") or ""))

    festival_today = ""
    tithi_today = ""
    try:
        cal = await fetch_tithi_festival(
            base_url=settings.vedastro_base_url,
            lat=lat_f,
            lon=lon_f,
            tz_offset=settings.default_tz_offset,
            ayanamsa=settings.vedastro_ayanamsa,
        )
        festival_today = cal.festival
        tithi_today = cal.tithi
    except Exception:
        pass

    _, language_name = _lang_for_user(profile)
    return {
        "status": "success",
        "calendar": build_daily_calendar(
            language=language_name,
            region=str(profile.get("region") or ""),
            tithi=tithi_today,
            festival=festival_today,
        ),
        "stories": search_library(str(profile.get("preferences") or profile.get("language") or ""), limit=6),
    }


@app.post("/report/analyze")
async def analyze_report(payload: dict[str, Any]):
    user_id = str(payload.get("user_id") or "").strip()
    report_text = _clean_text(str(payload.get("report_text") or ""))
    file_name = str(payload.get("file_name") or "report").strip() or "report"
    if not report_text:
        return {"status": "success", **_fallback_report_analysis("", {})}

    context = await _fetch_user_context(user_id) if user_id else {"user": {}, "medicines": []}
    profile = context.get("user") or {}
    medicines = ", ".join(
        f"{med.get('name', 'Medicine')} {med.get('dose', '')}".strip()
        for med in (context.get("medicines") or [])[:8]
    ) or "No medicines listed"

    system = (
        "You are Bhumi, helping a family manager review a parent's medical report. "
        "Do not diagnose. Keep the answer practical, warm, and short. "
        "Return exactly two sections using this format:\n"
        "SUMMARY: <1-2 short sentences>\n"
        "ADVICE: <1-2 short sentences with safe next steps, reminders, or medicine verification guidance>"
    )
    user_prompt = (
        f"Parent name: {profile.get('name', 'Parent')}\n"
        f"Current medicines: {medicines}\n"
        f"Report file: {file_name}\n"
        f"Extracted report text:\n{report_text}"
    )

    raw = ""
    if settings.groq_api_key:
        try:
            raw = await groq_chat_completion(
                settings.groq_api_key,
                model=settings.groq_model,
                system=system,
                user=user_prompt,
            )
        except Exception:
            logger.exception("Groq report analysis failed")
            raw = ""
    if not raw and settings.gemini_api_key:
        try:
            raw = await gemini_generate_text(
                api_key=settings.gemini_api_key,
                model=settings.gemini_model,
                system=system,
                user=user_prompt,
            )
        except Exception:
            logger.exception("Gemini report analysis failed")
            raw = ""

    parsed = _parse_report_analysis(raw, report_text, profile)

    extract_system = (
        "Extract prescribed medicines from this medical report text. "
        "Return one medicine per line with this exact pipe format and nothing else:\n"
        "name | dose | times comma separated in HH:MM if explicitly present else blank | instructions | condition"
    )
    extract_user = f"Report text:\n{report_text}"
    structured_raw = ""
    if settings.groq_api_key:
        try:
            structured_raw = await groq_chat_completion(
                settings.groq_api_key,
                model=settings.groq_model,
                system=extract_system,
                user=extract_user,
            )
        except Exception:
            logger.exception("Groq medicine extraction failed")
            structured_raw = ""
    if not structured_raw and settings.gemini_api_key:
        try:
            structured_raw = await gemini_generate_text(
                api_key=settings.gemini_api_key,
                model=settings.gemini_model,
                system=extract_system,
                user=extract_user,
            )
        except Exception:
            logger.exception("Gemini medicine extraction failed")
            structured_raw = ""

    return {"status": "success", **parsed, "suggested_medicines": _parse_medicine_suggestions(structured_raw, report_text)}


@app.post("/rppg/analyze")
async def analyze_rppg(request: Request):
    form = await request.form()
    user_id = str(form.get("user_id") or "").strip()
    file = form.get("video")
    if file is None or not hasattr(file, "read"):
        return JSONResponse(status_code=400, content={"status": "error", "message": "video file is required"})

    try:
        video_bytes = await file.read()
        result = analyze_rppg_video_bytes(video_bytes, file.filename or "face-video.mp4", settings.media_dir)
    except ValueError as exc:
        return JSONResponse(status_code=422, content={"status": "error", "message": str(exc)})
    except Exception as exc:
        message = str(exc)
        if "Invalid data found when processing input" in message:
            message = "Bhumi could not read that video. Please upload a short front-camera face video with a steady face and good light."
        return JSONResponse(status_code=500, content={"status": "error", "message": message})

    plot_url = f"{settings.base_url}/media/{result['plot_file']}"
    bpm = result["bpm"]
    sqi = result["sqi"]

    # Build detailed quality feedback
    quality_issues: list[str] = []
    if sqi < 0.15:
        quality_label = "Very Low"
        quality_issues.append("The signal was very weak — the face may not have been clearly visible.")
        quality_issues.append("Try with brighter, even lighting directly on your face.")
        quality_issues.append("Hold the phone steady and keep your face still for the full recording.")
    elif sqi < 0.4:
        quality_label = "Low"
        quality_issues.append("The signal was weak. Try better lighting and hold steady.")
    elif sqi < 0.65:
        quality_label = "Fair"
        quality_issues.append("Decent capture — a steadier position or brighter light would improve it.")
    else:
        quality_label = "Good"

    match_pct = min(round(sqi * 100), 100)

    note = (
        f"Experimental camera wellness check estimated pulse near {round(bpm)} BPM. "
        f"Signal quality: {quality_label} ({match_pct}% match). This is not a medical reading."
    )

    if user_id:
        try:
            async with httpx.AsyncClient(timeout=12) as client:
                await client.post(
                    f"{settings.data_service_url}/activity/{user_id}/status",
                    json={
                        "status": "okay",
                        "mood": "okay",
                        "note": note,
                    },
                )
                await client.post(
                    f"{settings.data_service_url}/conversations/{user_id}",
                    json={
                        "ts": datetime.now(timezone.utc).isoformat(),
                        "text_input": "[camera_wellness_check]",
                        "ai_response": note,
                        "mood": "okay",
                        "emotion": "neutral",
                        "source": "rppg",
                    },
                )
        except Exception:
            logger.exception("Failed to persist rPPG activity for user=%s", user_id)

        # Share rPPG report with caretaker/family via alerts service
        try:
            rppg_message = (
                f"Bhumi Camera Wellness Check for user {user_id}:\n"
                f"Estimated pulse: {round(result['bpm'])} BPM\n"
                f"Signal quality: {result['sqi']:.2f}\n"
                f"{note}\n\n"
                f"This is an experimental reading, not a medical diagnosis."
            )
            async with httpx.AsyncClient(timeout=15) as client:
                await client.post(
                    f"{settings.alerts_service_url}/report-share",
                    json={
                        "user_id": user_id,
                        "file_name": "Camera Wellness Check",
                        "summary": f"Estimated pulse: {round(result['bpm'])} BPM, Signal quality: {result['sqi']:.2f}",
                        "advice": "This is an experimental camera reading only. Please do not use for medical decisions.",
                        "severity": 40,
                    },
                )
        except Exception:
            logger.warning("Failed to share rPPG report with caretakers for user=%s", user_id, exc_info=True)

    return {
        "status": "success",
        "bpm": bpm,
        "sqi": sqi,
        "hrv": result["hrv"],
        "raw_bvp": result["raw_bvp"],
        "timestamps": result["timestamps"],
        "plot_url": plot_url,
        "note": note,
        "quality_label": quality_label,
        "match_pct": match_pct,
        "quality_issues": quality_issues,
        "medical_notice": "Experimental camera wellness check only. Do not use for diagnosis or emergency decisions.",
    }


@app.get("/report/pdf/{user_id}")
async def generate_pdf_report(user_id: str):
    """Generate a branded Bhumi wellness PDF report for sharing."""
    try:
        context = await _fetch_user_context(user_id)
    except Exception:
        context = {"user": {"user_id": user_id, "name": "Friend"}, "medicines": [], "recent_conversations": [], "memories": [], "activity": {}}

    profile = context["user"]

    # Fetch weekly report data from data service
    report_data: dict[str, Any] = {}
    alerts: list[dict[str, Any]] = []
    try:
        async with httpx.AsyncClient(timeout=15) as client:
            report_res = await client.get(f"{settings.data_service_url}/weekly-report/{user_id}")
            if report_res.is_success:
                report_data = report_res.json() or {}
            alerts_res = await client.get(f"{settings.data_service_url}/alerts/{user_id}", params={"limit": 10})
            if alerts_res.is_success:
                alerts = (alerts_res.json() or {}).get("items") or []
    except Exception:
        logger.warning("Could not fetch report data for PDF generation user=%s", user_id, exc_info=True)

    try:
        filename = generate_wellness_pdf(
            user_name=str(profile.get("name") or "Friend"),
            user_age=profile.get("age") or 72,
            user_language=str(profile.get("language") or "Hindi"),
            user_region=str(profile.get("region") or profile.get("city") or ""),
            report_data=report_data,
            medicines=context.get("medicines") or [],
            recent_alerts=alerts,
            out_dir=settings.media_dir,
        )
    except Exception as exc:
        logger.exception("PDF generation failed for user=%s", user_id)
        return JSONResponse(status_code=500, content={"status": "error", "message": str(exc)})

    pdf_url = f"{settings.base_url}/media/{filename}"
    return {
        "status": "success",
        "pdf_url": pdf_url,
        "filename": filename,
        "user_id": user_id,
        "user_name": str(profile.get("name") or "Friend"),
    }


@app.post("/voice")
async def voice(request: Request):
    user_id = "demo"
    text: str | None = None
    audio: UploadFile | None = None
    lat: float | None = None
    lon: float | None = None

    ctype = (request.headers.get("content-type") or "").lower()
    if "application/json" in ctype:
        body = await request.json()
        user_id = str(body.get("user_id") or user_id)
        text = body.get("text")
        if body.get("lat") is not None and body.get("lon") is not None:
            try:
                lat = float(body.get("lat"))
                lon = float(body.get("lon"))
            except Exception:
                lat = None
                lon = None
    else:
        form = await request.form()
        user_id = str(form.get("user_id") or user_id)
        text = form.get("text")
        _aud = form.get("audio")
        audio = _aud if hasattr(_aud, "filename") else None
        if form.get("lat") is not None and form.get("lon") is not None:
            try:
                lat = float(str(form.get("lat")))
                lon = float(str(form.get("lon")))
            except Exception:
                lat = None
                lon = None

    user_text = _clean_text(text or "")
    audio_bytes: bytes | None = None
    emotion_label = "neutral"

    if audio is not None:
        try:
            audio_bytes = await audio.read()
        except Exception:
            audio_bytes = None



    if not user_text and audio_bytes:
        try:
            stt = await transcribe_audio_bytes(
                audio_bytes,
                filename=audio.filename,
                elevenlabs_api_key=settings.elevenlabs_api_key,
                elevenlabs_model_id=settings.elevenlabs_stt_model_id,
            )
            user_text = _clean_text(stt.text or "")
        except Exception:
            return JSONResponse(
                status_code=400,
                content={"status": "error", "message": "Audio provided but STT is not enabled yet. Please type or enable Whisper."},
            )

    if audio_bytes:
        try:
            emotion = await infer_emotion_from_audio_bytes(audio_bytes)
            emotion_label = emotion.label or "neutral"
        except Exception:
            emotion_label = "neutral"

    if not user_text:
        return JSONResponse(status_code=400, content={"status": "error", "message": "Missing text"})

    try:
        context = await _fetch_user_context(user_id)
    except Exception:
        context = {
            "user": {"user_id": user_id, "name": "Friend", "language": "Hindi", "region": "Karnataka"},
            "medicines": [],
            "recent_conversations": [],
            "memories": [],
            "activity": {},
        }

    profile = context["user"]
    recent_conversations = context["recent_conversations"]
    medicines = context["medicines"]
    memories = context["memories"]

    if lat is None or lon is None:
        try:
            lat = float(profile.get("lat")) if profile.get("lat") is not None else None
            lon = float(profile.get("lon")) if profile.get("lon") is not None else None
        except Exception:
            lat = None
            lon = None
    if lat is None or lon is None:
        lat, lon = _default_coords_for_region(str(profile.get("region") or ""))

    base_prompt = load_system_prompt() or "You are ElderMind. Be warm, short, and comforting."
    weather_summary = "unknown"
    festival_today = ""
    tithi_today = ""

    if settings.openweather_api_key and lat is not None and lon is not None:
        try:
            wx = await fetch_openweather_summary(api_key=settings.openweather_api_key, lat=lat, lon=lon, lang="en")
            weather_summary = wx.summary
        except Exception:
            logger.warning("Weather fetch failed for lat=%s lon=%s", lat, lon, exc_info=True)
            weather_summary = "unknown"

    if lat is not None and lon is not None:
        try:
            cal = await fetch_tithi_festival(
                base_url=settings.vedastro_base_url,
                lat=lat,
                lon=lon,
                tz_offset=settings.default_tz_offset,
                ayanamsa=settings.vedastro_ayanamsa,
            )
            festival_today = cal.festival
            tithi_today = cal.tithi
        except Exception:
            logger.warning("VedAstro tithi fetch failed", exc_info=True)
            festival_today = ""
            tithi_today = ""

    tool_context = ""
    if settings.tavily_api_key and any(word in user_text.lower() for word in ("weather", "news", "latest", "today", "price", "score", "match", "cricket", "football", "ipl", "world cup", "election", "result")):
        try:
            results = await tavily_search(settings.tavily_api_key, user_text, max_results=3)
            if results:
                tool_context = "\nWEB_CONTEXT:\n" + "\n".join(
                    f"- {item.get('title', '')}: {str(item.get('content', ''))[:180]} ({item.get('url', '')})"
                    for item in results[:3]
                )
        except Exception:
            tool_context = ""

    cultural_context = ""
    if any(word in user_text.lower() for word in ("ramayana", "mahabharata", "gita", "doha", "chalisa", "story", "stories", "panchatantra", "birbal", "tenali")):
        matches = search_library(user_text, limit=3)
        if matches:
            cultural_context = "\nCULTURAL_LIBRARY:\n" + "\n".join(
                f"- {item.get('tradition')}: {item.get('title')} - {item.get('summary')} Moral: {item.get('moral')}"
                for item in matches
            )

    provisional = parse_markers(user_text)
    health_logs = _detect_health_logs(user_text)
    mood = _derive_mood(user_text, emotion_label, provisional)
    response_lang_code, response_language_name = _detect_runtime_language(user_text, profile)
    system = _build_system_prompt(
        base_prompt=base_prompt + tool_context + cultural_context,
        profile=profile,
        medicines=medicines,
        memories=memories,
        recent_conversations=recent_conversations,
        mood=mood,
        weather_summary=weather_summary,
        festival_today=festival_today,
        tithi_today=tithi_today,
        response_language_name=response_language_name,
    )

    raw = ""
    if settings.groq_api_key:
        try:
            raw = await groq_chat_completion(settings.groq_api_key, model=settings.groq_model, system=system, user=user_text)
        except Exception:
            logger.exception("Groq LLM call failed for user=%s", user_id)
            raw = ""

    if not raw and settings.gemini_api_key:
        try:
            raw = await gemini_generate_text(api_key=settings.gemini_api_key, model=settings.gemini_model, system=system, user=user_text)
        except Exception:
            logger.exception("Gemini LLM call failed for user=%s", user_id)
            raw = ""

    if not raw:
        logger.warning("All LLM providers failed for user=%s, using fallback reply", user_id)
        raw = _fallback_reply(user_text, profile, mood, health_logs, [], response_lang_code)

    parsed = parse_markers(raw)
    combined_health_logs = list(dict.fromkeys(health_logs + parsed.health_logs))
    final_mood = parsed.mood_logs[-1] if parsed.mood_logs else mood
    alerts = _derive_alerts(user_text, combined_health_logs, final_mood, parsed, recent_conversations)

    if alerts and not parsed.alerts:
        raw = f"{parsed.cleaned_text or raw} [ALERT: {alerts[0]}]"
        parsed = parse_markers(raw)

    speech_text = parsed.cleaned_text or raw
    mp3_name = synthesize_mp3(
        speech_text,
        lang=response_lang_code if response_lang_code != "en" else "en",
        out_dir=settings.media_dir,
        elevenlabs_api_key=settings.elevenlabs_api_key,
        elevenlabs_voice_id=settings.elevenlabs_tts_voice_id,
        elevenlabs_model_id=settings.elevenlabs_tts_model_id,
    )
    audio_url = f"{settings.base_url}/media/{mp3_name}"

    memory_items = _extract_memories(user_text, profile)
    try:
        async with httpx.AsyncClient(timeout=12) as client:
            await client.post(
                f"{settings.data_service_url}/conversations/{user_id}",
                json={
                    "ts": datetime.now(timezone.utc).isoformat(),
                    "text_input": user_text,
                    "ai_response": speech_text,
                    "mood": final_mood,
                    "emotion": emotion_label,
                    "health_logs": combined_health_logs,
                    "mood_logs": [final_mood],
                    "alerts": alerts,
                    "source": "voice",
                    "context": {
                        "weather": weather_summary,
                        "festival": festival_today,
                        "tithi": tithi_today,
                    },
                },
            )
            for issue in alerts:
                await client.post(
                    f"{settings.data_service_url}/alerts/{user_id}",
                    json={
                        "time_created": datetime.now(timezone.utc).isoformat(),
                        "type": "ai_marker",
                        "message": issue,
                        "severity": 90 if issue in {"urgent_health", "urgent_help"} else 70,
                    },
                )
            for memory in memory_items:
                await client.post(f"{settings.data_service_url}/memory/{user_id}", json=memory)
    except Exception:
        logger.exception("Failed to persist conversation/alerts/memories for user=%s", user_id)

    if alerts:
        await _post_caretaker_alert(user_id, ", ".join(alerts))

    return {
        "status": "success",
        "text": speech_text,
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "mood": final_mood,
        "emotion": emotion_label,
        "response_language": response_language_name,
        "response_language_code": response_lang_code,
        "response_speech_lang": _browser_lang_for_code(response_lang_code),
        "alert_sent": bool(alerts),
        "alert_severity": 90 if any(item in {"urgent_health", "urgent_help"} for item in alerts) else (70 if alerts else 0),
        "logs": {
            "health": combined_health_logs,
            "mood": [final_mood],
            "alerts": alerts,
            "memories": memory_items,
        },
        "audio_url": audio_url,
    }
