from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class EmotionResult:
    label: str
    score: float | None = None


async def infer_emotion_from_audio_bytes(audio_bytes: bytes) -> EmotionResult:
    """
    Optional SpeechBrain emotion inference (heavy deps).
    If not installed, return neutral.
    """
    try:
        from speechbrain.inference.interfaces import foreign_class  # type: ignore
    except Exception:
        return EmotionResult(label="neutral", score=None)

    import tempfile
    from pathlib import Path

    with tempfile.NamedTemporaryFile(delete=False, suffix=".wav") as f:
        f.write(audio_bytes)
        wav_path = f.name

    # This uses a pretrained classifier; may download models on first run.
    classifier = foreign_class(source="speechbrain/emotion-recognition-wav2vec2-IEMOCAP", pymodule_file="custom_interface.py", classname="CustomInterface")
    out = classifier.classify_file(wav_path)
    # Best-effort normalization of outputs
    label = "neutral"
    score = None
    try:
        if isinstance(out, tuple) and len(out) >= 3:
            label = str(out[2][0])
            score = float(out[1][0])
    except Exception:
        label = "neutral"
        score = None
    return EmotionResult(label=label, score=score)

