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
BUILT_FRONTEND = ROOT / "web/dist"
if BUILT_FRONTEND.exists():
    app.mount("/assets", StaticFiles(directory=BUILT_FRONTEND / "assets"), name="frontend-assets")


@app.get("/")
def index():
    built_index = BUILT_FRONTEND / "index.html"
    return FileResponse(built_index if built_index.exists() else ROOT / "web/index.html")


@app.get("/swisscam-logo.png")
def logo():
    built_logo = BUILT_FRONTEND / "swissscam-logo.png"
    source_logo = ROOT / "web/public/swissscam-logo.png"
    if built_logo.exists():
        return FileResponse(built_logo, media_type="image/png")
    if source_logo.exists():
        return FileResponse(source_logo, media_type="image/png")
    raise HTTPException(status_code=404, detail="Logo asset not found")


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
