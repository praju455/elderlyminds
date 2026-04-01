from __future__ import annotations

import logging
from dataclasses import dataclass

import httpx

logger = logging.getLogger("ai_service.stt")


@dataclass(frozen=True)
class STTResult:
    text: str
    language: str | None = None


async def _transcribe_with_elevenlabs(
    audio_bytes: bytes,
    *,
    filename: str | None,
    api_key: str,
    model_id: str,
) -> STTResult:
    files = {
        "file": (filename or "audio.webm", audio_bytes, "audio/webm"),
    }
    data = {
        "model_id": model_id,
    }
    async with httpx.AsyncClient(timeout=90) as client:
        res = await client.post(
            "https://api.elevenlabs.io/v1/speech-to-text",
            headers={"xi-api-key": api_key},
            data=data,
            files=files,
        )
        res.raise_for_status()
        payload = res.json() or {}
    return STTResult(
        text=str(payload.get("text") or "").strip(),
        language=str(payload.get("language_code") or "").strip() or None,
    )


async def _transcribe_with_whisper(audio_bytes: bytes, *, filename: str | None = None) -> STTResult:
    try:
        import whisper  # type: ignore
    except Exception as e:  # pragma: no cover
        raise RuntimeError("Whisper STT not installed") from e

    import asyncio
    import tempfile
    from pathlib import Path

    suffix = Path(filename or "audio.webm").suffix or ".webm"
    with tempfile.NamedTemporaryFile(delete=False, suffix=suffix) as f:
        f.write(audio_bytes)
        tmp = f.name

    def _run_whisper() -> dict:
        model = whisper.load_model("base")
        return model.transcribe(tmp)

    result = await asyncio.to_thread(_run_whisper)
    text = (result.get("text") or "").strip()
    lang = result.get("language")
    return STTResult(text=text, language=lang)


async def transcribe_audio_bytes(
    audio_bytes: bytes,
    *,
    filename: str | None = None,
    elevenlabs_api_key: str | None = None,
    elevenlabs_model_id: str = "scribe_v1",
) -> STTResult:
    if elevenlabs_api_key:
        try:
            return await _transcribe_with_elevenlabs(
                audio_bytes,
                filename=filename,
                api_key=elevenlabs_api_key,
                model_id=elevenlabs_model_id,
            )
        except Exception:
            logger.exception("ElevenLabs STT failed, falling back to Whisper")
    return await _transcribe_with_whisper(audio_bytes, filename=filename)
