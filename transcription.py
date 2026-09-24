import os
from functools import lru_cache
from pathlib import Path
from collections.abc import Iterator

from faster_whisper import WhisperModel

from schemas import Transcript, TranscriptSegment


@lru_cache(maxsize=1)
def _load_model() -> WhisperModel:
    model_size = os.getenv("WHISPER_MODEL_SIZE", "base")
    return WhisperModel(model_size, device="cpu", compute_type="int8")


@lru_cache(maxsize=8)
def _transcribe_segments(audio_path: Path) -> tuple[TranscriptSegment, ...]:
    return tuple(transcribe_stream(audio_path))


def transcribe_stream(audio_path: Path) -> Iterator[TranscriptSegment]:
    """Yield short, word-timed updates for playback and incremental detection."""
    if not audio_path.is_file():
        raise FileNotFoundError(audio_path)

    whisper_segments, _ = _load_model().transcribe(str(audio_path), beam_size=5, word_timestamps=True)
    for segment in whisper_segments:
        if segment.words:
            words = []
            for index, word in enumerate(segment.words):
                words.append(word)
                # Preserve whole words and their timestamps; do not guess timings.
                if word.end - words[0].start >= 3 or index == len(segment.words) - 1:
                    text = "".join(item.word for item in words).strip()
                    if text:
                        yield TranscriptSegment(text=text, start_seconds=words[0].start, end_seconds=word.end)
                    words = []
            continue
        text = segment.text.strip()
        if text:
            yield TranscriptSegment(
                text=text,
                start_seconds=segment.start,
                end_seconds=segment.end,
            )


def transcribe(audio_path: Path, up_to_seconds: float | None = None) -> Transcript:
    """Transcribe a local file and return only completed segments up to a cutoff."""
    all_segments = _transcribe_segments(audio_path)
    segments = [
        segment
        for segment in all_segments
        if up_to_seconds is None or segment.end_seconds <= up_to_seconds
    ]
    return Transcript(
        text=" ".join(segment.text for segment in segments),
        segments=segments,
    )
