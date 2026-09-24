import os
from functools import lru_cache
from pathlib import Path

from faster_whisper import WhisperModel


@lru_cache(maxsize=1)
def _load_model() -> WhisperModel:
    model_size = os.getenv("WHISPER_MODEL_SIZE", "base")
    return WhisperModel(model_size, device="cpu", compute_type="int8")


def transcribe(audio_path: Path) -> str:
    """Transcribe a local audio file with a cached Whisper model."""
    if not audio_path.is_file():
        raise FileNotFoundError(audio_path)

    segments, _ = _load_model().transcribe(str(audio_path), beam_size=5)
    return " ".join(segment.text.strip() for segment in segments).strip()
