import os
from functools import lru_cache
from pathlib import Path
from collections.abc import Iterator

from dotenv import load_dotenv
from faster_whisper import WhisperModel

from schemas import Transcript, TranscriptSegment

load_dotenv()


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
        text="\n\n".join(segment.text for segment in segments),
        segments=segments,
    )


@lru_cache(maxsize=1)
def _whisperx_device() -> str:
    import torch

    return os.getenv("WHISPERX_DEVICE", "cuda" if torch.cuda.is_available() else "cpu")


@lru_cache(maxsize=1)
def _load_whisperx_model():
    import whisperx

    device = _whisperx_device()
    compute_type = os.getenv("WHISPERX_COMPUTE_TYPE", "float16" if device == "cuda" else "int8")
    model_size = os.getenv("WHISPER_MODEL_SIZE", "base")
    return whisperx.load_model(model_size, device, compute_type=compute_type)


@lru_cache(maxsize=1)
def _load_diarization_model(token: str, device: str):
    from whisperx.diarize import DiarizationPipeline

    return DiarizationPipeline(token=token, device=device)


def transcribe_with_speakers(audio_path: Path) -> Transcript:
    """Transcribe a complete file and attach local speaker labels with WhisperX."""
    if not audio_path.is_file():
        raise FileNotFoundError(audio_path)

    token = os.getenv("HF_TOKEN")
    if not token:
        raise RuntimeError("HF_TOKEN is required to download the local speaker-diarization model")

    import whisperx

    device = _whisperx_device()
    audio = whisperx.load_audio(str(audio_path))
    result = _load_whisperx_model().transcribe(
        audio,
        batch_size=int(os.getenv("WHISPERX_BATCH_SIZE", "8")),
        language=os.getenv("WHISPER_LANGUAGE", "en"),
    )
    diarization = _load_diarization_model(token, device)(audio)
    result = whisperx.assign_word_speakers(diarization, result)

    segments = [
        TranscriptSegment(
            text=segment["text"].strip(),
            start_seconds=float(segment["start"]),
            end_seconds=float(segment["end"]),
            speaker=segment.get("speaker", "unknown"),
        )
        for segment in result["segments"]
        if segment.get("text", "").strip()
    ]
    return Transcript(
        text="\n\n".join(segment.text for segment in segments),
        segments=segments,
    )
