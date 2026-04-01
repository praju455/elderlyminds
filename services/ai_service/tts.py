from __future__ import annotations

from pathlib import Path
from uuid import uuid4

import httpx
from gtts import gTTS


def _save_gtts(text: str, *, lang: str, out_dir: str) -> str:
    Path(out_dir).mkdir(parents=True, exist_ok=True)
    fname = f"tts_{uuid4().hex}.mp3"
    path = Path(out_dir) / fname
    tts = gTTS(text=text, lang=lang, slow=False)
    tts.save(str(path))
    return fname


def synthesize_mp3(
    text: str,
    *,
    lang: str,
    out_dir: str,
    elevenlabs_api_key: str | None = None,
    elevenlabs_voice_id: str | None = None,
    elevenlabs_model_id: str | None = None,
) -> str:
    Path(out_dir).mkdir(parents=True, exist_ok=True)
    fname = f"tts_{uuid4().hex}.mp3"
    path = Path(out_dir) / fname

    if elevenlabs_api_key and elevenlabs_voice_id:
        try:
            response = httpx.post(
                f"https://api.elevenlabs.io/v1/text-to-speech/{elevenlabs_voice_id}",
                headers={
                    "xi-api-key": elevenlabs_api_key,
                    "Content-Type": "application/json",
                    "Accept": "audio/mpeg",
                },
                json={
                    "text": text,
                    "model_id": elevenlabs_model_id or "eleven_multilingual_v2",
                    "voice_settings": {
                        "stability": 0.45,
                        "similarity_boost": 0.8,
                    },
                },
                timeout=60,
            )
            response.raise_for_status()
            path.write_bytes(response.content)
            return fname
        except Exception:
            pass

    return _save_gtts(text, lang=lang, out_dir=out_dir)
