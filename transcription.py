import os
from functools import lru_cache
from pathlib import Path

from faster_whisper import WhisperModel

from schemas import Transcript, TranscriptSegment


@lru_cache(maxsize=1)
def _load_model() -> WhisperModel:
    model_size = os.getenv("WHISPER_MODEL_SIZE", "base")
    return WhisperModel(model_size, device="cpu", compute_type="int8")


def transcribe(audio_path: Path) -> Transcript:
    """Transcribe a local audio file and preserve Whisper segment timings."""
    if not audio_path.is_file():
        raise FileNotFoundError(audio_path)

    whisper_segments, _ = _load_model().transcribe(str(audio_path), beam_size=5)
    segments = [
        TranscriptSegment(
            text=segment.text.strip(),
            start_seconds=segment.start,
            end_seconds=segment.end,
        )
        for segment in whisper_segments
        if segment.text.strip()
    ]
    return Transcript(
        text=" ".join(segment.text for segment in segments),
        segments=segments,
    )
