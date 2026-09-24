import json
import tempfile
from pathlib import Path
from collections.abc import Iterator

from fastapi import FastAPI, HTTPException
from fastapi import File, UploadFile
from fastapi.responses import FileResponse
from fastapi.responses import StreamingResponse
from fastapi.staticfiles import StaticFiles

from detector import detect
from schemas import (
    AnalyzeRequest,
    DetectionResult,
    Transcript,
    TranscriptUpdate,
    TranscribeRequest,
)
from transcription import transcribe, transcribe_stream

ROOT = Path(__file__).parent
app = FastAPI(title="swissscam skeleton")
app.mount("/audio", StaticFiles(directory=ROOT / "data/audio"), name="audio")


@app.get("/")
def index():
    return FileResponse(ROOT / "web/index.html")


@app.post("/api/transcribe")
def transcribe_audio(request: TranscribeRequest) -> Transcript:
    if request.audio_id != "demo":
        raise HTTPException(status_code=404, detail="Unknown demo audio")
    return transcribe(ROOT / "data/audio/demo.wav", request.up_to_seconds)


@app.post("/api/transcribe/upload")
def transcribe_upload(audio: UploadFile = File(...)) -> StreamingResponse:
    """Stream completed Whisper segments for an uploaded audio file as SSE."""
    suffix = Path(audio.filename or "audio.wav").suffix or ".wav"
    temporary_file = tempfile.NamedTemporaryFile(delete=False, suffix=suffix)
    temporary_path = Path(temporary_file.name)

    try:
        temporary_file.write(audio.file.read())
        temporary_file.close()
    except Exception:
        temporary_file.close()
        temporary_path.unlink(missing_ok=True)
        raise

    def events() -> Iterator[str]:
        transcript_parts: list[str] = []
        try:
            for segment in transcribe_stream(temporary_path):
                transcript_parts.append(segment.text)
                event = TranscriptUpdate(
                    type="segment",
                    text=" ".join(transcript_parts),
                    segment=segment,
                )
                yield f"data: {event.model_dump_json()}\n\n"

            finished = TranscriptUpdate(type="done", text=" ".join(transcript_parts))
            yield f"data: {json.dumps(finished.model_dump())}\n\n"
        finally:
            temporary_path.unlink(missing_ok=True)

    return StreamingResponse(events(), media_type="text/event-stream")


@app.post("/api/analyze")
def analyze(request: AnalyzeRequest) -> DetectionResult:
    return detect(request.transcript)
